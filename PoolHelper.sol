// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad, fromUint256, fromInt256, intoInt256, POSITIVE_ZERO, POSITIVE_ONE, POSITIVE_TWO, HALF} from "src/types/ABDKMathQuad/Quad.sol";
import {
    LOG1PPC,
    JUMPS,
    MIN_SPLITS,
    EPOCH,
    DEFLATOR_STEP_0,
    DEFLATOR_STEP_1,
    DEFLATOR_STEP_2,
    DEFLATOR_STEP_3,
    DEFLATOR_STEP_4,
    DEFLATOR_STEP_5,
    DEFLATOR_STEP_6,
    DEFLATOR_STEP_7,
    DEFLATOR_STEP_8,
    DEFLATOR_STEP_9,
    DEFLATOR_STEP_10,
    DEFLATOR_STEP_11,
    DEFLATOR_STEP_12
} from "src/Constants.sol";
import {BoxcarTubFrame} from "src/libraries/internal/BoxcarTubFrame.sol";
import {JumpyFallback} from "src/libraries/internal/JumpyFallback.sol";
import {GrowthSplitFrame} from "src/libraries/internal/GrowthSplitFrame.sol";
import {PiecewiseGrowthNew} from "src/libraries/internal/DeadlineJumps.sol";
import {BucketRolling} from "src/libraries/internal/BucketRolling.sol";
import {TUBS, TICK_SUB_SLITS} from "src/Constants.sol";
import {floor, max} from "src/types/ABDKMathQuad/Math.sol";
import {PoolState} from "src/interfaces/IInfinityPoolState.sol";

using JumpyFallback for JumpyFallback.Info;
using GrowthSplitFrame for GrowthSplitFrame.Info;
using BucketRolling for BucketRolling.Info;
using BoxcarTubFrame for BoxcarTubFrame.Info;
using PiecewiseGrowthNew for PiecewiseGrowthNew.Info;

Quad constant O = POSITIVE_ZERO;

function subSplits(int256 splits) pure returns (int256) {
    return splits - int256(MIN_SPLITS);
}

function exFee(Quad fees) pure returns (Quad) {
    return POSITIVE_ONE - fees;
}

function logBin(int256 splits) pure returns (Quad) {
    return LOG1PPC / fromUint256(1 << uint256(subSplits(splits)));
}

function h(int256 splits) pure returns (Quad) {
    return (logBin(splits) / POSITIVE_TWO).exp();
}

function BINS(int256 splits) pure returns (int256) {
    return int256(1 << uint256(splits));
}

function binStrike(int256 splits, int256 bin) pure returns (Quad) {
    return (logBin(splits) * (fromInt256(bin) - (fromInt256(BINS(splits)) / POSITIVE_TWO) + HALF)).exp();
}

function sqrtStrike(int256 splits, int256 bin) pure returns (Quad) {
    return (logBin(splits) / POSITIVE_TWO * (fromInt256(bin) - (fromInt256(BINS(splits)) / POSITIVE_TWO) + HALF)).exp();
}

function mid(int256 splits, int256 tickBin) pure returns (Quad) {
    return binStrike(splits, tickBin);
}

function fracBin(int256 splits, Quad startPrice) pure returns (Quad) {
    return startPrice.log() / logBin(splits) + fromInt256(BINS(splits)) / POSITIVE_TWO;
}

function fracPrice(int256 splits, int256 tickBin, Quad binFrac) pure returns (Quad) {
    return (logBin(splits) * (fromInt256(tickBin) + binFrac - fromInt256(BINS(splits)) / fromInt256(2))).exp();
}

function tickBin(Quad fracBin) pure returns (int256) {
    return intoInt256(fracBin);
}

function tickBin(int256 splits, Quad startPrice) pure returns (int256) {
    return tickBin(fracBin(splits, startPrice));
}

function fluidAt(BoxcarTubFrame.Info storage self, int256 bin, int256 splits) view returns (Quad) {
    return BoxcarTubFrame.apply_(self, bin >> uint256(subSplits(splits)));
}

function liquid(BoxcarTubFrame.Info storage self, int256 bin, int256 splits, Quad gamma, Quad deflator) view returns (Quad) {
    return max(fluidAt(self, bin, splits) - gamma * deflator, O);
}

function gamma(JumpyFallback.Info storage lent, BoxcarTubFrame.Info storage offRamp, int256 poolEra, int256 splits, int256 tickBin) returns (Quad) {
    return lent.nowAt(poolEra, splits, tickBin) - offRamp.active(splits, tickBin);
}

function spotFee(GrowthSplitFrame.Info[2] storage fees, int256 splits, bool inToken, Quad accrual, Quad) {
    PiecewiseGrowthNew.Info storage fee = fees[inToken ? 1 : 0].live(splits);
    fee.accrued = fee.accrued + accrual;
}

function edgePrice(int256 edge) pure returns (Quad) {
    return (LOG1PPC * fromInt256(edge)).exp();
}

function edgeSqrtPrice(int256 edge) pure returns (Quad) {
    return (LOG1PPC / POSITIVE_TWO * fromInt256(edge)).exp();
}

function binLowSqrt(int256 splits, int256 bin) pure returns (Quad) {
    return (logBin(bin) / POSITIVE_TWO * (fromInt256(bin) - fromInt256(BINS(splits)) / POSITIVE_TWO)).exp();
}

function tubLowSqrt(int256 tub) pure returns (Quad) {
    return edgeSqrtPrice(tub - TUBS / 2);
}

function tubLowTick(int256 tub) pure returns (int256) {
    return ((tub - TUBS / 2) << TICK_SUB_SLITS);
}

function lowEdgeTub(int256 edge) pure returns (int256) {
    return edge + TUBS / 2;
}

// inverse of lowEdgeTub
function tubLowEdge(int256 tub) pure returns (int256) {
    return tub - TUBS / 2;
}

function tickSqrtPrice(int256 tick) pure returns (Quad) {
    return ((logTick() / POSITIVE_TWO * fromInt256(tick))).exp();
}

function binLowTick(int256 splits, int256 bin) pure returns (int256) {
    return (bin - BINS(splits) / 2) << (TICK_SUB_SLITS - uint256(subSplits(splits)));
}

function eraDay(int256 era) pure returns (int256) {
    return era >> 11;
}

function dayEra(int256 day) pure returns (int256) {
    return day << 11;
}

function dayEras() pure returns (int256) {
    return dayEra(1);
}

function dateEra(Quad date) pure returns (int256) {
    return floor(date * fromInt256(dayEras()));
}

function eraDate(int256 era) pure returns (Quad) {
    return fromInt256(era) / fromInt256(dayEras());
}

function timestampDate(uint256 timestamp) pure returns (Quad) {
    return fromInt256(int256(timestamp) - EPOCH) / fromUint256(1 days);
}

function floorMod(int256 x, int256 y) pure returns (int256) {
    int256 mod = (x % y);

    if ((mod ^ y) < 0 && mod != 0) mod = (mod + y);

    return mod;
}

function floorDiv(int256 x, int256 y) pure returns (int256) {
    int256 r = (x / y);

    if ((x ^ y) < 0 && (r * y != x)) r = (r - 1);

    return r;
}

function logTick() pure returns (Quad) {
    return LOG1PPC / fromUint256(1 << TICK_SUB_SLITS);
}

function getDeflatorStep(uint256 index) pure returns (Quad) {
    require(index <= 12, "Index out of bounds");

    if (index < 6) {
        if (index < 3) {
            if (index == 0) return DEFLATOR_STEP_0;
            else if (index == 1) return DEFLATOR_STEP_1;
            else return DEFLATOR_STEP_2;
        } else {
            if (index == 3) return DEFLATOR_STEP_3;
            else if (index == 4) return DEFLATOR_STEP_4;
            else return DEFLATOR_STEP_5;
        }
    } else {
        if (index < 9) {
            if (index == 6) return DEFLATOR_STEP_6;
            else if (index == 7) return DEFLATOR_STEP_7;
            else return DEFLATOR_STEP_8;
        } else {
            if (index == 9) return DEFLATOR_STEP_9;
            else if (index == 10) return DEFLATOR_STEP_10;
            else if (index == 11) return DEFLATOR_STEP_11;
            else return DEFLATOR_STEP_12;
        }
    }
}

library PoolHelper {
    function epsilon_(PoolState storage pool) public view returns (Quad) {
        return pool.epsilon;
    }

    function logBin(PoolState storage pool) public view returns (Quad) {
        return _logBin(pool);
    }

    function BINS(PoolState storage pool) public view returns (int256) {
        return _BINS(pool);
    }

    function sqrtMid(PoolState storage pool) public view returns (Quad) {
        return _sqrtMid(pool);
    }

    function mid(PoolState storage pool) public view returns (Quad) {
        return _mid(pool);
    }

    function liquid(PoolState storage pool) public returns (Quad) {
        return _liquid(pool);
    }
}

function _logBin(PoolState storage pool) view returns (Quad) {
    return logBin(pool.splits);
}

function _BINS(PoolState storage pool) view returns (int256) {
    return BINS(pool.splits);
}

function _sqrtMid(PoolState storage pool) view returns (Quad) {
    return sqrtStrike(pool.splits, pool.tickBin);
}

function _mid(PoolState storage pool) view returns (Quad) {
    return mid(pool.splits, pool.tickBin);
}

function _liquid(PoolState storage pool) returns (Quad) {
    Quad gamma = gamma(pool.lent, pool.offRamp, pool.era, pool.splits, pool.tickBin);
    return liquid(pool.minted, pool.tickBin, pool.splits, gamma, pool.deflator);
}