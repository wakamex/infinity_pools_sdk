// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {
    Quad,
    fromInt256,
    POSITIVE_ZERO,
    HALF,
    POSITIVE_ONE,
    POSITIVE_TWO,
    POSITIVE_FOUR,
    POSITIVE_EIGHT,
    POSITIVE_NINE,
    POSITIVE_INFINITY,
    POSITIVE_EIGHT_OVER_NINE,
    POSITIVE_ONE_OVER_FOUR,
    wrap
} from "src/types/ABDKMathQuad/Quad.sol";
import {sqrt, exp} from "src/types/ABDKMathQuad/Math.sol";
import "src/types/ABDKMathQuad/MathExtended.sol" as MathExtended;
import {OptInt256} from "src/types/Optional/OptInt256.sol";
import {PoolState} from "src/interfaces/IInfinityPoolState.sol";
import {
    Z,
    I,
    LAMBDA,
    MIN_RATE,
    UTILISATION_CAP,
    PERIODIC_APPROX_CONSTANT_0,
    PERIODIC_APPROX_CONSTANT_1,
    PERIODIC_APPROX_CONSTANT_2,
    PERIODIC_APPROX_CONSTANT_3,
    PERIODIC_APPROX_CONSTANT_4,
    PERIODIC_APPROX_CONSTANT_5,
    PERIODIC_APPROX_CONSTANT_6,
    PERIODIC_APPROX_CONSTANT_7
} from "src/Constants.sol";
import {DeadlineJumps, DeadlineSet} from "src/libraries/internal/DeadlineJumps.sol";
import {Swapper} from "src/libraries/external/Swapper.sol";
import {SwapperInternal} from "src/libraries/external/SwapperInternal.sol";
import {BINS, binStrike, sqrtStrike, logBin, fluidAt, fracPrice} from "src/libraries/helpers/PoolHelper.sol";
import {BucketRolling} from "src/libraries/internal/BucketRolling.sol";
import {JumpyFallback} from "src/libraries/internal/JumpyFallback.sol";
import {PoolState} from "src/interfaces/IInfinityPoolState.sol";
import {UserPay} from "src/libraries/internal/UserPay.sol";

using {MathExtended.expm1} for Quad;

library NewLoan {
    using BucketRolling for BucketRolling.Info;
    using JumpyFallback for JumpyFallback.Info;
    using Swapper for SwapperInternal.Info;
    using SwapperInternal for SwapperInternal.Info;

    error UnavailableLockInPeriod(Quad lockingEnd);
    error UnsupportedLockInPeriod(Quad lockingEnd);
    error InvalidOwedPotential();
    error InvalidBinRange(int256 startBin, int256 stopBin);
    error InvalidLendToken();
    error UnalignableStrikeOutside(int256 strikeBin, int256 startBin, int256 stopBin);
    error UnalignedStrike(int256 strikeBin, int256 startBin);
    error StrikeAtBinZeroNotAllowed();
    error LiquidityRangeContainsPrice(Quad fracPrice);
    error NaNIsNotAllowed();
    error SwapperCreationNotEnabledYet();
    error UtilisationCapBreached(Quad badUsed);

    function tilter(int256 splits, int256 bin, Quad strike) internal pure returns (Quad) {
        return sqrtStrike(splits, bin) - strike / sqrtStrike(splits, bin);
    }

    function quadVar(PoolState storage pool) internal view returns (Quad) {
        return pool.dayMove.sum(pool);
    }

    function max(Quad x, Quad y) internal pure returns (Quad) {
        return x > y ? x : y;
    }

    struct ComputeLentAtIndexLocalVars {
        Quad inflator;
        Quad rate;
        Quad logm;
        Quad theta;
        Quad cr;
        int256 bin;
        Quad oldUsed;
        Quad minted;
        Quad virtualOwed;
        Quad square;
        Quad newUsed;
    }

    struct LockingEndLocalVars {
        Quad logw;
        Quad geoMean;
        Quad shiftMnot1;
        Quad shiftMis1;
        bool canSkip;
    }

    struct ComputeLentAtIndexParams {
        uint256 index;
        Quad owedPotentialAtIndex;
        int256 startBin;
        Quad lockinEnd;
        Quad logm;
        Quad deltaLogm;
        Quad q;
    }

    function computeLentAtIndex(PoolState storage pool, ComputeLentAtIndexParams memory params, LockingEndLocalVars memory lockingEndVars)
        private
        returns (Quad)
    {
        ComputeLentAtIndexLocalVars memory vars;

        vars.inflator = (POSITIVE_ONE / pool.deflator);

        vars.rate = POSITIVE_ONE / (POSITIVE_TWO * params.q * ((params.q - HALF) * params.logm).exp() - POSITIVE_ONE);

        if ((params.lockinEnd <= POSITIVE_ONE)) {
            lockingEndVars.logw = params.logm;

            if ((params.lockinEnd > POSITIVE_ZERO)) {
                if (!lockingEndVars.canSkip) {
                    lockingEndVars.geoMean = ((params.lockinEnd * quadVar(pool))).sqrt();
                    lockingEndVars.shiftMnot1 = (
                        PERIODIC_APPROX_CONSTANT_0 + (PERIODIC_APPROX_CONSTANT_1 * lockingEndVars.geoMean)
                            + (PERIODIC_APPROX_CONSTANT_2 + quadVar(pool) * PERIODIC_APPROX_CONSTANT_3) * params.lockinEnd
                    ) * lockingEndVars.geoMean;
                    lockingEndVars.shiftMis1 = (
                        PERIODIC_APPROX_CONSTANT_4 + (PERIODIC_APPROX_CONSTANT_5 * lockingEndVars.geoMean)
                            + (PERIODIC_APPROX_CONSTANT_6 + quadVar(pool) * PERIODIC_APPROX_CONSTANT_7) * params.lockinEnd
                    ) * lockingEndVars.geoMean;
                    lockingEndVars.canSkip = true;
                }
                lockingEndVars.logw = max((params.logm + lockingEndVars.shiftMnot1), lockingEndVars.shiftMis1);
                if (!((lockingEndVars.logw > POSITIVE_ZERO))) revert UnavailableLockInPeriod(params.lockinEnd);
            }

            vars.rate = POSITIVE_ONE
                / (
                    ((params.q + HALF) * ((params.q - HALF) * lockingEndVars.logw).expm1())
                        - ((params.q - HALF) * (-(params.q + HALF) * lockingEndVars.logw).expm1())
                );
        } else {
            // params.lockinEnd != POSITIVE_INFINITY does not work!!
            if ((params.lockinEnd.unwrap() != POSITIVE_INFINITY.unwrap())) revert UnsupportedLockInPeriod(params.lockinEnd);
        }
        vars.rate = max(vars.rate, MIN_RATE);
        params.logm = (params.logm + params.deltaLogm);
        vars.theta = (POSITIVE_ONE + (POSITIVE_EIGHT_OVER_NINE * vars.rate));
        vars.cr = (vars.rate / POSITIVE_NINE);
        vars.bin = (params.startBin + int256(params.index));
        vars.oldUsed = (pool.used.nowAt(pool.era, pool.splits, vars.bin) * pool.deflator);
        vars.minted = fluidAt(pool.minted, vars.bin, pool.splits);
        vars.virtualOwed = (((vars.theta + (vars.cr / (POSITIVE_ONE - vars.oldUsed))) * vars.oldUsed) + (params.owedPotentialAtIndex / vars.minted));
        vars.square = ((vars.virtualOwed - vars.theta) + vars.cr);
        vars.newUsed = (
            (((vars.virtualOwed + POSITIVE_ONE) + vars.rate) - (((vars.square * vars.square) + ((POSITIVE_FOUR * vars.cr) * vars.theta))).sqrt())
                / (POSITIVE_TWO * vars.theta)
        );
        if( vars.newUsed > UTILISATION_CAP )
            revert UtilisationCapBreached(vars.newUsed);
        return (((vars.newUsed - vars.oldUsed) * vars.minted) * vars.inflator);
    }

    struct NewLoanParams {
        Quad[] owedPotential;
        int256 startBin;
        int256 strikeBin;
        Quad tokenMix;
        Quad lockinEnd;
        OptInt256 deadEra;
        bool token;
        OptInt256 twapUntil;
    }

    struct NewLoanLocalVars {
        int256 stopBin;
        bool lendToken;
        Quad offset;
        Quad q;
        Quad logm;
        Quad deltaLogm;
        Quad inflator;
        Quad[] lent;
        SwapperInternal.Info swapper;
    }

    function newLoan(PoolState storage pool, NewLoanParams memory params) external returns (UserPay.Info memory) {
        if (params.tokenMix.isNaN() && params.lockinEnd.isNaN()) revert NaNIsNotAllowed();
        if (pool.swappers.length == 0) revert SwapperCreationNotEnabledYet();
        NewLoanLocalVars memory vars;

        if (!((params.owedPotential.length > 0) && (params.lockinEnd >= POSITIVE_ZERO))) revert InvalidOwedPotential();
        for (int256 i = 0; (i < int256(params.owedPotential.length)); i = (i + 1)) {
            if (((params.owedPotential[uint256(i)]) < POSITIVE_ZERO)) revert InvalidOwedPotential();
        }
        vars.stopBin = (params.startBin + int256(params.owedPotential.length));
        if (!((0 <= params.startBin) && (vars.stopBin <= BINS(pool.splits)))) revert InvalidBinRange(params.startBin, vars.stopBin);
        vars.lendToken = Z;
        if ((vars.stopBin <= pool.tickBin)) {
            vars.lendToken = I;
        } else {
            if ((params.startBin > pool.tickBin)) vars.lendToken = Z;
            else revert LiquidityRangeContainsPrice(fracPrice(pool.splits, pool.tickBin, pool.binFrac));
        }

        if ((vars.stopBin > (params.startBin + 1))) {
            if (!(params.startBin < params.strikeBin && ((params.strikeBin < (vars.stopBin - 1))))) {
                revert UnalignableStrikeOutside(params.strikeBin, params.startBin, vars.stopBin);
            }
            for (int256 index = 0; (index < int256(params.owedPotential.length)); index = (index + 1)) {
                vars.offset = (
                    vars.offset
                        + (
                            params.owedPotential[uint256(index)]
                                * tilter(pool.splits, (params.startBin + index), binStrike(pool.splits, params.strikeBin))
                        )
                );
            }
            if ((vars.offset > POSITIVE_ZERO)) {
                params.owedPotential[0] =
                    (params.owedPotential[0] + (vars.offset / -tilter(pool.splits, (params.startBin), binStrike(pool.splits, params.strikeBin))));
            } else {
                if ((vars.offset < POSITIVE_ZERO)) {
                    uint256 i = (params.owedPotential.length - 1);
                    params.owedPotential[i] =
                        params.owedPotential[i] + (-vars.offset / tilter(pool.splits, vars.stopBin - 1, binStrike(pool.splits, params.strikeBin)));
                }
            }
        } else {
            if ((params.strikeBin != params.startBin)) revert UnalignedStrike(params.strikeBin, params.startBin);
            if ((params.strikeBin == 0)) revert StrikeAtBinZeroNotAllowed();
        }
        vars.q = (((POSITIVE_ONE_OVER_FOUR) + ((POSITIVE_TWO * LAMBDA / quadVar(pool))))).sqrt();
        vars.logm = logBin(pool.splits) * ((fromInt256((params.startBin - pool.tickBin)).abs()) - HALF);
        if ((vars.lendToken == Z)) {
            vars.deltaLogm = logBin(pool.splits);
        } else {
            if ((vars.lendToken == I)) vars.deltaLogm = -logBin(pool.splits);
            else revert InvalidLendToken();
        }

        vars.lent = new Quad[](params.owedPotential.length);

        LockingEndLocalVars memory lockingEndVars;
        ComputeLentAtIndexParams memory computeLentAtIndexParams =
            ComputeLentAtIndexParams(0, params.owedPotential[0], params.startBin, params.lockinEnd, vars.logm, vars.deltaLogm, vars.q);
        for (uint256 index = 0; (index < params.owedPotential.length); index = (index + 1)) {
            computeLentAtIndexParams.index = index;
            computeLentAtIndexParams.owedPotentialAtIndex = params.owedPotential[index];
            vars.lent[index] = computeLentAtIndex(pool, computeLentAtIndexParams, lockingEndVars);
        }
        SwapperInternal.Info memory swapperInfo = SwapperInternal.Info({
            owner: msg.sender,
            startBin: int32(params.startBin),
            strikeBin: int32(params.strikeBin),
            tokenMix: params.tokenMix,
            unlockDate: pool.date + params.lockinEnd,
            deadEra: params.deadEra,
            token: params.token,
            twapUntil: params.twapUntil,
            owed: params.owedPotential,
            lent: vars.lent,
            minted: new Quad[](params.owedPotential.length),
            oweLimit: POSITIVE_ZERO,
            lentCapacity0: POSITIVE_ZERO,
            lentCapacity1: POSITIVE_ZERO
        });
        pool.swappers.push(SwapperInternal.init(swapperInfo, pool));

        SwapperInternal.Info storage swapper = pool.swappers[pool.swappers.length - 1];
        swapper.created(pool);

        return (
            UserPay.Info(
                (swapper.backing(pool, Z) - (vars.lendToken == Z ? (swapper.lentCapacity0 * pool.deflator) : POSITIVE_ZERO)),
                (swapper.backing(pool, I) - (vars.lendToken == I ? (swapper.lentCapacity1 * pool.deflator) : POSITIVE_ZERO))
            )
        );
    }
}