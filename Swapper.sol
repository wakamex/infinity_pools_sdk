// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad, fromInt256, POSITIVE_ZERO, POSITIVE_ONE, fromUint256} from "src/types/ABDKMathQuad/Quad.sol";
import {OptInt256, wrap} from "src/types/Optional/OptInt256.sol";
import {PoolState} from "src/interfaces/IInfinityPoolState.sol";
import {Z, I, LAMBDA, JUMPS, LN2, NEVER_AGO} from "src/Constants.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {DeadlineJumps, DeadlineSet, PiecewiseCurve, DropsGroup} from "src/libraries/internal/DeadlineJumps.sol";
import {sqrtStrike, fluidAt, eraDate} from "src/libraries/helpers/PoolHelper.sol";
import {max} from "src/types/ABDKMathQuad/Math.sol";
import {GrowthSplitFrame} from "src/libraries/internal/GrowthSplitFrame.sol";
import {JumpyFallback} from "src/libraries/internal/JumpyFallback.sol";
import {DropFaberTotals} from "src/libraries/internal/DropFaberTotals.sol";
import {JumpyAnchorFaber} from "src/libraries/internal/JumpyAnchorFaber.sol";
import {UserPay} from "src/libraries/internal/UserPay.sol";
import {AnyPayoff} from "src/libraries/internal/Payoff.sol";
import {GapStagedFrame} from "src/libraries/internal/GapStagedFrame.sol";
import {max as maxInt32} from "src/libraries/internal/Utils.sol";
import {NettingGrowth} from "src/libraries/internal/NettingGrowth.sol";
import {SwapperInternal} from "./SwapperInternal.sol";
import {NewLoan} from "./NewLoan.sol";

library Swapper {
    using SafeCast for int256;
    using GapStagedFrame for GapStagedFrame.Info;
    using GrowthSplitFrame for GrowthSplitFrame.Info;
    using JumpyFallback for JumpyFallback.Info;
    using DropFaberTotals for DropFaberTotals.Info;
    using JumpyAnchorFaber for JumpyAnchorFaber.Info;
    using DeadlineSet for DeadlineSet.Info;
    using DeadlineJumps for DeadlineSet.Info;
    using NettingGrowth for NettingGrowth.Info;

    error OnlyOwnerAllowed();
    error SwapperLocked(Quad currentDate, Quad unlockDate);
    error CannotWithDrawFromFixedLoan();
    error TokenMixIsNaN();
    error SwapperCreationIsAlreadyEnabled();

    /**
     * @dev This function allows to change some key aspects of the swapper: the time when the swapper expires (and the nature of the loan related to it, in case deadEra is set from not None to None and viceversa) and the TWAP
     *     @dev Changing the other aspects like time when the swapper expires and the TWAP might result in more tokens to be provided
     *     @dev This function can also be used to swap the swapper but using `reflow()` for this purpose is more gas efficient
     */
    function reset(SwapperInternal.Info storage self, PoolState storage pool, OptInt256 deadEra, Quad tokenMix, bool fixedToken, OptInt256 twapUntil)
        external
        returns (UserPay.Info memory)
    {
        if (!self.deadEra.isDefined()) revert CannotWithDrawFromFixedLoan();
        if (tokenMix.isNaN()) revert TokenMixIsNaN();
        if (msg.sender != self.owner) revert OnlyOwnerAllowed();

        SwapperInternal.checkAlive(self, pool);
        Quad oldBacking0 = SwapperInternal.backing(self, pool, Z);

        Quad oldBacking1 = SwapperInternal.backing(self, pool, I);

        // Updates the flows and fees with respect to the current state of the Swapper, before any changes
        SwapperInternal.borrow(self, pool, false);
        SwapperInternal.flow(self, pool, false);
        self.deadEra = deadEra;
        self.tokenMix = tokenMix;
        self.twapUntil = twapUntil;
        self.token = fixedToken;
        // Validates the new state of the Swapper
        SwapperInternal.validate(self, pool);
        // Updates the flows and fees with respect to the new state of the Swapper, after any changes
        SwapperInternal.borrow(self, pool, true);
        SwapperInternal.flow(self, pool, true);

        // Compute the amount of tokens needed to back the new position of the swapper
        return UserPay.Info((SwapperInternal.backing(self, pool, Z) - oldBacking0), (SwapperInternal.backing(self, pool, I) - oldBacking1));
    }

    /**
     * @dev Used to change the TWAP and to perform swaps inside the swapper
     *     @dev The swap is done by changing the `tokenMix`
     *     @dev The operations allowed by this function are a subset of the ones allowed by `reset()` but it is less gas expensive because of this reason
     */
    function reflow(SwapperInternal.Info storage self, PoolState storage pool, Quad tokenMix, bool fixedToken, OptInt256 twapUntil)
        external
        returns (UserPay.Info memory)
    {
        if (tokenMix.isNaN()) revert TokenMixIsNaN();
        if (msg.sender != self.owner) revert OnlyOwnerAllowed();
        Quad oldBacking0 = SwapperInternal.backing(self, pool, Z);
        Quad oldBacking1 = SwapperInternal.backing(self, pool, I);

        SwapperInternal.flow(self, pool, false);
        self.tokenMix = tokenMix;
        self.twapUntil = twapUntil;
        self.token = fixedToken;
        SwapperInternal.validate(self, pool);
        SwapperInternal.flow(self, pool, true);
        return UserPay.Info((SwapperInternal.backing(self, pool, Z) - oldBacking0), (SwapperInternal.backing(self, pool, I) - oldBacking1));
    }

    function created(SwapperInternal.Info storage self, PoolState storage pool) public returns (SwapperInternal.Info storage) {
        SwapperInternal.validate(self, pool);
        SwapperInternal.borrow(self, pool, true);
        SwapperInternal.flow(self, pool, true);
        return self;
    }

    struct UnwindLocalVars {
        Quad release0;
        Quad release1;
        int32 midIndex;
    }

    function unwind(SwapperInternal.Info storage self, PoolState storage pool) external returns (UserPay.Info memory) {
        UnwindLocalVars memory vars;
        if (msg.sender != self.owner) revert OnlyOwnerAllowed();
        SwapperInternal.checkAlive(self, pool);
        if (pool.date < self.unlockDate) revert SwapperLocked(pool.date, self.unlockDate);
        if (!self.deadEra.isDefined()) revert CannotWithDrawFromFixedLoan();

        vars.release0 = SwapperInternal.backing(self, pool, Z);
        vars.release1 = SwapperInternal.backing(self, pool, I);

        vars.midIndex = pool.tickBin - self.startBin;

        for (uint256 index = 0; index < self.lent.length && int256(index) < vars.midIndex; index++) {
            vars.release1 = vars.release1 - pool.epsilon * self.lent[index] * sqrtStrike(pool.splits, self.startBin + int256(index)) * pool.deflator;
        }

        for (uint256 index = uint256(int256(maxInt32(int32(0), vars.midIndex + 1))); index < self.lent.length; index++) {
            vars.release0 = vars.release0 - pool.epsilon * self.lent[index] / sqrtStrike(pool.splits, self.startBin + int256(index)) * pool.deflator;
        }

        if (0 <= vars.midIndex && uint256(int256(vars.midIndex)) < self.lent.length) {
            Quad sqrtMid = sqrtStrike(pool.splits, pool.tickBin);
            vars.release1 = vars.release1 - pool.binFrac * pool.epsilon * self.lent[uint256(int256(vars.midIndex))] * sqrtMid * pool.deflator;
            vars.release0 =
                vars.release0 - (POSITIVE_ONE - pool.binFrac) * pool.epsilon * self.lent[uint256(int256(vars.midIndex))] / sqrtMid * pool.deflator;
        }

        SwapperInternal.borrow(self, pool, false);
        SwapperInternal.flow(self, pool, false);
        self.deadEra = NEVER_AGO;

        return UserPay.Info(-vars.release0, -vars.release1);
    }

    function enableSwapperCreation(PoolState storage pool) external {
        if (pool.swappers.length > 0) revert SwapperCreationIsAlreadyEnabled();
        SwapperInternal.Info memory swapperInfo;
        pool.swappers.push(swapperInfo);
    }
}