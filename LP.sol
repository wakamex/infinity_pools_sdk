// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad, fromInt256, POSITIVE_ZERO, POSITIVE_ONE, POSITIVE_TWO, HALF} from "src/types/ABDKMathQuad/Quad.sol";
import {ceil} from "src/types/ABDKMathQuad/Math.sol";
import {UserPay} from "src/libraries/internal/UserPay.sol";
import {PoolState} from "src/interfaces/IInfinityPoolState.sol";
import {TUBS, JUMPS, WORD_SIZE, Z, I} from "src/Constants.sol";
import {DailyJumps} from "src/libraries/internal/DailyJumps.sol";
import {GrowthSplitFrame} from "src/libraries/internal/GrowthSplitFrame.sol";
import {DeadlineFlag} from "src/libraries/internal/DeadlineFlag.sol";
import {JumpyAnchorFaber, Anchor, AnchorSet} from "src/libraries/internal/JumpyAnchorFaber.sol";
import {SignedMath} from "@openzeppelin/contracts/utils/math/SignedMath.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {BoxcarTubFrame} from "src/libraries/internal/BoxcarTubFrame.sol";
import {GrowthSplitFrame} from "src/libraries/internal/GrowthSplitFrame.sol";
import {eraDate, subSplits, sqrtStrike, logBin, BINS, tubLowSqrt, tubLowTick} from "src/libraries/helpers/PoolHelper.sol";
import {deadEra} from "src/libraries/helpers/DeadlineHelper.sol";
import {OptInt256} from "src/types/Optional/OptInt256.sol";
import {GapStagedFrame} from "src/libraries/internal/GapStagedFrame.sol";
import {JumpyFallback} from "src/libraries/internal/JumpyFallback.sol";

import {EachPayoff} from "src/libraries/internal/EachPayoff.sol";
import {FloatBits, SparseFloat, QuadPacker} from "src/libraries/internal/SparseFloat.sol";
import {Capper} from "src/libraries/internal/Capper.sol";
import {LAMBDA} from "src/Constants.sol";

import {LPShed} from "./LPShed.sol";
import {UserPay} from "src/libraries/internal/UserPay.sol";

library LP {
    using DeadlineFlag for DeadlineFlag.Info;
    using BoxcarTubFrame for BoxcarTubFrame.Info;
    using JumpyAnchorFaber for JumpyAnchorFaber.Info;
    using GrowthSplitFrame for GrowthSplitFrame.Info;
    using GapStagedFrame for GapStagedFrame.Info;
    using JumpyFallback for JumpyFallback.Info;
    using AnchorSet for AnchorSet.Info;
    using Capper for Capper.Info;
    using SafeCast for uint256;
    using SafeCast for int256;
    using FloatBits for Quad;

    enum Stage {
        Join,
        Earn,
        Exit
    }

    struct Info {
        //Stage enum parameters
        int128 lower0;
        int128 upper0;
        int128 lower1;
        int128 upper1;
        Quad liquidity;
        Quad growPast0;
        Quad growPast1;
        Quad drainDate;
        int32 earnEra;
        int32 startTub;
        int32 stopTub;
        // It should take 1 slot since address is 20 bytes and Stage is an enum with 3 values and therefore represented by a unit8
        address owner;
        Stage stage;
    }

    error InvalidPourArguments();
    error MustWaitTillTailEraToStartDraining(int256 tailEra, int256 poolEra);
    error MustWaitTillEarnEraToStartTapping(int256 earnEra, int256 poolEra);
    error LiquidityPositionAlreadyDraining();
    error StageNotJoined();
    error OnlyOwnerAllowed();
    error liquidityIsNaN();
    error GetPourQuantitiesResult(int256, int256);

    function init(int256 startTub, int256 stopTub, Quad liquidity, Stage stage, int256 earnEra) internal view returns (Info memory) {
        Info memory lp;
        lp.owner = msg.sender;
        lp.startTub = int32(startTub);
        lp.stopTub = int32(stopTub);
        lp.liquidity = liquidity;
        lp.stage = stage;
        lp.earnEra = int32(earnEra);
        return lp;
    }

    function accrued(Info storage self, PoolState storage pool) internal returns (Quad, Quad) {
        GrowthSplitFrame.Info storage fees0 = pool.fees[0];
        GrowthSplitFrame.Info storage fees1 = pool.fees[1];
        Quad res1 = fees0.accruedRange(pool, self.startTub, self.stopTub);
        Quad res2 = fees1.accruedRange(pool, self.startTub, self.stopTub);
        return (res1, res2);
    }

    function earn(Info storage self, PoolState storage pool, bool flush) internal returns (Quad, Quad) {
        if (self.stage == Stage.Earn) {
            Quad oldAccrued0 = self.growPast0;
            Quad oldAccrued1 = self.growPast1;

            (Quad newAccrued0, Quad newAccrued1) = accrued(self, pool);

            if (flush) {
                self.stage = Stage.Earn; // (mchen) extraneous
                self.growPast0 = newAccrued0;
                self.growPast1 = newAccrued1;
            }

            return ((newAccrued0 - oldAccrued0).max(POSITIVE_ZERO) * self.liquidity, (newAccrued1 - oldAccrued1).max(POSITIVE_ZERO) * self.liquidity);
        } else {
            return (POSITIVE_ZERO, POSITIVE_ZERO);
        }
    }

    struct PourLocalVars {
        int256 startBin;
        int256 stopBin;
        Quad reserve0;
        Quad reserve1;
        Quad yield0;
        Quad yield1;
        int256 tailEra;
        Quad tailYield0;
        Quad yieldFlow0;
        Quad tailYield1;
        Quad yieldFlow1;
        Quad yieldRatio;
    }

    function bins(int256 splits, int256 startTub, int256 stopTub) public pure returns (int256, int256) {
        return ((startTub << subSplits(splits).toUint256()), (stopTub << subSplits(splits).toUint256()));
    }

    // startBin and stopBin can be calculated from startTub and stopTub.
    // but it may be cheaper to pass them
    function reserves(PoolState storage pool, int256 startTub, int256 stopTub, int256 startBin, int256 stopBin) internal view returns (Quad, Quad) {
        Quad reserve0 = POSITIVE_ZERO;
        Quad reserve1 = POSITIVE_ZERO;

        if ((startBin > pool.tickBin)) {
            reserve0 = ((POSITIVE_ONE / tubLowSqrt(startTub)) - (POSITIVE_ONE / tubLowSqrt(stopTub)));
            reserve1 = POSITIVE_ZERO;
        } else {
            if ((stopBin <= pool.tickBin)) {
                reserve0 = POSITIVE_ZERO;
                reserve1 = (tubLowSqrt(stopTub) - tubLowSqrt(startTub));
            } else {
                reserve0 = (
                    ((POSITIVE_ONE / lowSqrtBin(pool, pool.tickBin)) - (POSITIVE_ONE / tubLowSqrt(stopTub)))
                        - ((pool.epsilon / sqrtStrike(pool.splits, pool.tickBin)) * pool.binFrac)
                );
                reserve1 = (
                    (lowSqrtBin(pool, pool.tickBin) - tubLowSqrt(startTub)) + ((pool.epsilon * sqrtStrike(pool.splits, pool.tickBin)) * pool.binFrac)
                );
            }
        }
        return (reserve0, reserve1);
    }

    /**
     * @dev Adds liquidity to the pool
     *     @dev The precision of the liquidity range is in the `TUBS` scale, which is more coarse grained than the `BINS` since they are separated by 1% increments in the log price space, scale and the `TICKS` scale
     *     @param startTub The lower bound of the liquidity range
     *     @param stopTub The upper bound of the liquidity range
     *     @param liquidity The liquidity to be added
     */
    function pour(PoolState storage pool, int256 startTub, int256 stopTub, Quad liquidity) external returns (UserPay.Info memory) {
        if (liquidity.isNaN()) revert liquidityIsNaN();
        PourLocalVars memory vars;

        if (((((startTub < 0) || (startTub >= stopTub)) || (stopTub > TUBS)) || (liquidity <= POSITIVE_ZERO))) revert InvalidPourArguments();

        pool.minted.addRange(startTub, stopTub, liquidity);
        (vars.startBin, vars.stopBin) = bins(pool.splits, startTub, stopTub);
        (vars.reserve0, vars.reserve1) = reserves(pool, startTub, stopTub, vars.startBin, vars.stopBin);

        if( pool.swappers.length == 0 ) {
            Info memory nullLp;
            pool.lps.push(nullLp);
            pool.lpCount++;

            Info storage lp = pool.lps[pool.lpCount - 1];
            lp.owner = msg.sender;
            lp.startTub = int32(startTub);
            lp.stopTub = int32(stopTub);
            lp.liquidity = liquidity;
            lp.stage = Stage.Earn;
            (Quad accrued0, Quad accrued1) = accrued(lp, pool);
            lp.growPast0 = accrued0;
            lp.growPast1 = accrued1;
            return UserPay.Info((liquidity * vars.reserve0), (liquidity * vars.reserve1));
        }

        // The `tailEra` effect

        // Compute the era corresponding to the last jump in the future, based on the current pool era
        vars.tailEra = deadEra(pool.era, (JUMPS - 1));

        // In this case `true` is associated to the `tailEra`
        pool.resets.assign(pool.era, true, vars.tailEra);

        for (int256 i = 0; (i < pool.flowHat.length.toInt256()); i = (i + 1)) {
            JumpyAnchorFaber.Info storage temp = pool.flowHat[i.toUint256()];
            temp.setEnd(pool, vars.tailEra, pool.tickBin);
        }

        // Fees calculation

        // Setup fees accounting for the new liquidity
        pool.joinStaged.stage(pool, vars.startBin, vars.stopBin, liquidity);
        GrowthSplitFrame.Info storage fees0 = pool.fees[0];
        GrowthSplitFrame.Info storage fees1 = pool.fees[1];
        JumpyAnchorFaber.Info storage flowHat0 = pool.flowHat[0];
        JumpyAnchorFaber.Info storage flowHat1 = pool.flowHat[1];

        // Computing the estimated yield in token0 and token1 for the liquidity added
        // In token0 for the sub-range above the pool price and
        // In token1 for the sub-range below the pool price
        vars.yield0 = fees0.sumTail(pool, SignedMath.max(vars.startBin, pool.tickBin), vars.stopBin);
        vars.yield1 = fees1.sumTail(pool, vars.startBin, SignedMath.min(vars.stopBin, pool.tickBin));

        if (((vars.startBin <= pool.tickBin) && (pool.tickBin < vars.stopBin))) {
            // If the liquidity range includes the pool price

            vars.tailYield0 = fees0.tailAt(pool, pool.tickBin);
            vars.yieldFlow0 = ((vars.tailYield0 / pool.epsilon) * liquidity);
            vars.tailYield1 = fees1.tailAt(pool, pool.tickBin);
            vars.yieldFlow1 = ((vars.tailYield1 / pool.epsilon) * liquidity);

            flowHat0.lateExpire(pool.era, vars.yieldFlow0, pool.splits, pool.tickBin, vars.tailEra);
            flowHat1.lateExpire(pool.era, vars.yieldFlow1, pool.splits, pool.tickBin, vars.tailEra);
            vars.yieldRatio = (vars.yieldFlow0 * sqrtStrike(pool.splits, pool.tickBin));

            pool.owed.expireOne(pool.era, pool.splits, vars.yieldRatio.neg(), pool.tickBin, vars.tailEra);

            // NOTE: The `binFrac` represents the intra-bin price and is such that
            // - when `binFrac=0` the bin liquidity is all token0
            // - when `binFrac=1` the bin liquidity is all token1

            // In the yield related calculations above, the effect of `binFrac` is not taken into account, this is done here

            // Adjusting the yield related to token0 for the `binFrac`
            vars.yield0 = (vars.yield0 - (vars.tailYield0 * pool.binFrac));
            Anchor.Info storage temp0 = pool.flowHat[0].drops._apply(pool.era, vars.tailEra);
            temp0.halfsum = (temp0.halfsum + (vars.yieldFlow0 * pool.binFrac));

            // Adjusting the yield related to token1 for the `binFrac`
            vars.yield1 = (vars.yield1 + (vars.tailYield1 * pool.binFrac));
            Anchor.Info storage temp1 = pool.flowHat[1].drops._apply(pool.era, vars.tailEra);
            temp1.halfsum = (temp1.halfsum - (vars.yieldFlow1 * pool.binFrac));
        }

        // Creating the LP tracking accounting object
        Info memory lp = init(startTub, stopTub, liquidity, Stage.Join, vars.tailEra);
        pool.lps.push(lp);
        pool.lpCount++;

        Quad tailDeflator = (-eraDate(vars.tailEra)).exp2();

        return
            UserPay.Info((liquidity * (vars.reserve0 + (vars.yield0 * tailDeflator))), (liquidity * (vars.reserve1 + (vars.yield1 * tailDeflator))));
    }

    /**
     *  Copied from pour() with some irrelevant state-changing code removed.
     *  This function does change the state (in sumTail) but the changes are
     *  immaterial in that they simply update the lazy data structures.
     */
    function getPourQuantities(PoolState storage pool, int256 startTub, int256 stopTub, Quad liquidity) public returns (UserPay.Info memory) {
        PourLocalVars memory vars;

        if (((((startTub < 0) || (startTub >= stopTub)) || (stopTub > TUBS)) || (liquidity <= POSITIVE_ZERO))) revert InvalidPourArguments();

        // TODO: move the following code to a common function to be shared
        // between pour() and getPourQuantities. This refactor will come
        // after current PR passes the (new) unit tests. This way, we compare
        // the results of getPourQuantities against those from the original
        // pour().
        (vars.startBin, vars.stopBin) = bins(pool.splits, startTub, stopTub);
        (vars.reserve0, vars.reserve1) = reserves(pool, startTub, stopTub, vars.startBin, vars.stopBin);

        vars.tailEra = deadEra(pool.era, (JUMPS - 1));

        GrowthSplitFrame.Info storage fees0 = pool.fees[0];
        GrowthSplitFrame.Info storage fees1 = pool.fees[1];

        vars.yield0 = fees0.sumTail(pool, SignedMath.max(vars.startBin, pool.tickBin), vars.stopBin);
        vars.yield1 = fees1.sumTail(pool, vars.startBin, SignedMath.min(vars.stopBin, pool.tickBin));

        Quad tailDeflator = (-eraDate(vars.tailEra)).exp2();

        return
            UserPay.Info((liquidity * (vars.reserve0 + (vars.yield0 * tailDeflator))), (liquidity * (vars.reserve1 + (vars.yield1 * tailDeflator))));
    }

    function getPourQuantitiesReverts(PoolState storage pool, int256 startTub, int256 stopTub, Quad liquidity) external {
        UserPay.Info memory userPay = getPourQuantities(pool, startTub, stopTub, liquidity);
        (int256 pay0, int256 pay1) = UserPay.translateQuantities(userPay, pool);
        revert GetPourQuantitiesResult(pay0, pay1);
    }

    function lowSqrtBin(PoolState storage pool, int256 bin) internal view returns (Quad) {
        return (((logBin(pool.splits) / POSITIVE_TWO) * fromInt256((bin - BINS(pool.splits) / (2))))).exp();
    }

    struct DrainLocalVars {
        Stage stage;
        int256 tailEra;
        int128 exponent;
        int256 lowerTick;
        int128 lower0;
        int128 lower1;
        int256 upperTick;
        int128 upper0;
        int128 upper1;
        Quad earned0;
        Quad earned1;
    }

    /**
     * @dev Drains liquidity from the pool associated to a given LP position
     *     @dev Draining liquidity is a process that takes some time to be completed
     *     @param lpNum The LP position number
     */
    function drain(PoolState storage pool, uint256 lpNum) external returns (UserPay.Info memory) {
        if (msg.sender != pool.lps[lpNum].owner) revert OnlyOwnerAllowed();
        DrainLocalVars memory vars;

        // The `stage` represents the LP position state, it can be
        // - Join: just added liquidity
        // - Earn: earning from deposited liquidity
        // - Exit: draining liquidity, no interests since the liquidity is locked and can't be lent out so not accruing interests
        vars.stage = pool.lps[lpNum].stage;

        if (vars.stage == Stage.Join) {
            // Liquidity just added
            // It is not possible to immediately remove liquidity once added, need to wait until a specific era, which is the LP `earnEra` is reached
            vars.tailEra = pool.lps[lpNum].earnEra;
            // If the LP `earnEra` has not been reached yet, it is not possible to proceed with draining the position
            if (pool.era < vars.tailEra) revert MustWaitTillTailEraToStartDraining(vars.tailEra, pool.era);
        } else {
            // If the current position is already draining, it cannot be drained again
            if (vars.stage == Stage.Exit) revert LiquidityPositionAlreadyDraining();
        }

        pool.minted.addRange(pool.lps[lpNum].startTub, pool.lps[lpNum].stopTub, pool.lps[lpNum].liquidity.neg());
        // Removing all of the LP liquidity in one shot from the tracker related to the available liquidity, by minting negative liquidity
        pool.offRamp.addRange(pool.lps[lpNum].startTub, pool.lps[lpNum].stopTub, pool.lps[lpNum].liquidity / pool.deflator);

        vars.exponent = int128(ceil((pool.date.neg() + HALF))) - int128(WORD_SIZE);

        // Tick corresponding to the startTub
        vars.lowerTick = tubLowTick(pool.lps[lpNum].startTub);
        vars.lower0 = EachPayoff.capperBegin(pool, vars.lowerTick, Z, vars.exponent);

        // NOTE: Handling the `startTub=0` edge case
        vars.lower1 =
            pool.lps[lpNum].startTub > 0 ? EachPayoff.capperBegin(pool, vars.lowerTick, I, vars.exponent) : ~pool.deflator.truncate(vars.exponent);

        // Tick corresponding to the stopTub
        vars.upperTick = tubLowTick(pool.lps[lpNum].stopTub);

        // NOTE: Handling the `stopTub=TUBS` edge case
        vars.upper0 =
            pool.lps[lpNum].stopTub < TUBS ? EachPayoff.capperBegin(pool, vars.upperTick, Z, vars.exponent) : ~pool.deflator.truncate(vars.exponent);
        vars.upper1 = EachPayoff.capperBegin(pool, vars.upperTick, I, vars.exponent);

        // Computed the earned amounts in token0 and token1
        (vars.earned0, vars.earned1) = earn(pool.lps[lpNum], pool, true);

        // Tracking the LP position entered the Drain state
        pool.lps[lpNum].stage = Stage.Exit;
        pool.lps[lpNum].lower0 = vars.lower0;
        pool.lps[lpNum].upper0 = vars.upper0;
        pool.lps[lpNum].lower1 = vars.lower1;
        pool.lps[lpNum].upper1 = vars.upper1;

        // Tracking the date when the drain started
        pool.lps[lpNum].drainDate = pool.date;

        // Returning the earned money to the LPer (paying negative amount means transferring money from the pool to the LPer)
        return UserPay.Info(vars.earned0.neg(), vars.earned1.neg());
    }

    function collect(PoolState storage pool, uint256 lpNum) external returns (UserPay.Info memory) {
        if (msg.sender != pool.lps[lpNum].owner) revert OnlyOwnerAllowed();

        LP.Info storage lp = pool.lps[lpNum];

        Quad gained0 = POSITIVE_ZERO;
        Quad gained1 = POSITIVE_ZERO;

        if ((lp.stage == Stage.Join)) {
            gained0 = POSITIVE_ZERO;
            gained1 = POSITIVE_ZERO;
        } else {
            if ((lp.stage == Stage.Earn)) (gained0, gained1) = earn(lp, pool, true);
            else (gained0, gained1) = LPShed.shed(lp, pool, true);
        }
        return UserPay.Info(gained0.neg(), gained1.neg());
    }

    function tap(PoolState storage pool, uint256 lpNum) external {
        LP.Info storage lp = pool.lps[lpNum];

        Stage stage = lp.stage;

        if ((stage == Stage.Join)) {
            if ((pool.era < lp.earnEra)) revert MustWaitTillEarnEraToStartTapping(lp.earnEra, pool.era);
        } else {
            revert StageNotJoined();
        }
        lp.stage = Stage.Earn;
        (Quad accrued0, Quad accrued1) = accrued(lp, pool);
        lp.growPast0 = accrued0;
        lp.growPast1 = accrued1;
    }
}