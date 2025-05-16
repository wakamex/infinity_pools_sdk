// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {PoolState} from "src/interfaces/IInfinityPoolState.sol";
import {Quad, POSITIVE_ZERO, POSITIVE_ONE, fromInt256} from "src/types/ABDKMathQuad/Quad.sol";
import {OptQuad, toOptQuad} from "src/types/Optional/OptQuad.sol";
import {max, min, exp, log, abs} from "src/types/ABDKMathQuad/Math.sol";
import {Z, I} from "src/Constants.sol";
import {GapStagedFrame} from "src/libraries/internal/GapStagedFrame.sol";
import {GrowthSplitFrame} from "src/libraries/internal/GrowthSplitFrame.sol";
import {UserPay} from "src/libraries/internal/UserPay.sol";
import {JumpyFallback} from "src/libraries/internal/JumpyFallback.sol";
import {BucketRolling} from "src/libraries/internal/BucketRolling.sol";
import {EachPayoff} from "src/libraries/internal/EachPayoff.sol";
import {liquid, mid, sqrtStrike, exFee, gamma, spotFee, BINS, O, PoolHelper} from "src/libraries/helpers/PoolHelper.sol";
import {PiecewiseGrowthNew} from "src/libraries/internal/DeadlineJumps.sol";

library Spot {
    using GapStagedFrame for GapStagedFrame.Info;
    using GrowthSplitFrame for GrowthSplitFrame.Info;
    using JumpyFallback for JumpyFallback.Info;
    using BucketRolling for BucketRolling.Info;
    using EachPayoff for PoolState;
    using PoolHelper for PoolState;

    error InvalidTickBin(int256 tickBin);
    error InvalidPushAmount();

    function updateFees(PoolState storage self, bool isUp) internal {
        self.fees[0].move(self, isUp);
        self.fees[1].move(self, isUp);
    }

    function _uptick(PoolState storage self) internal {
        if (self.tickBin >= ((BINS(self.splits) - 1))) revert InvalidTickBin(self.tickBin);

        self.joinStaged.flush(self, self.tickBin + 1);
        updateFees(self, true);
        self.tickBin = (self.tickBin + 1);
        self.binFrac = POSITIVE_ZERO;
    }

    function _downtick(PoolState storage self) internal {
        if (self.tickBin <= (0)) revert InvalidTickBin(self.tickBin);
        self.joinStaged.flush(self, self.tickBin - 1);
        updateFees(self, false);
        self.tickBin = (self.tickBin - 1);
        self.binFrac = POSITIVE_ONE;
    }

    function onSlip(PoolState storage pool, Quad qMove) public {
        if (qMove >= POSITIVE_ZERO) pool.dayMove.add(pool, qMove * pool.move2Var);
    }

    struct SpotSwapParams {
        Quad shove;
        bool ofToken; //token of push amount (true if token1, false if token0)
        OptQuad limitPrice;
        OptQuad remainingAmount; // used if user wants to have this much of remainingAmount relative to last action
    }

    event SpotSwapEvent(SpotSwapParams params, address receiver, UserPay.Info swapped);

    struct SwapLocalVars {
        bool pushing;
        Quad maxTokens;
        Quad input;
        Quad output;
        Quad varMove;
        bool pullToken;
        UserPay.Info transfer;
        Quad lastPrice;
        Quad liquid;
        Quad outFactor;
        Quad qEnd;
        Quad sweepPrice;
        Quad qNew;
        Quad qStep;
        Quad endPrice;
        Quad inFactor;
        Quad stepInput;
        Quad sweepInput;
        Quad qNew_;
        Quad qStep_;
        Quad stepOutput;
        Quad charged;
        Quad gained;
        OptQuad limitPrinv;
        Quad lastPrinv;
        Quad sweepPrinv;
        Quad endPrinv;
    }

    function swap(PoolState storage pool, Quad shove, bool token, OptQuad limitPrice) public returns (UserPay.Info memory) {
        SwapLocalVars memory vars;
        vars.pushing = shove > O;
        vars.maxTokens = abs(shove);
        vars.input = O;
        vars.output = O;
        vars.varMove = O;
        vars.pullToken = vars.pushing ? !token : token;
        if (!vars.pullToken) {
            vars.lastPrice = exp(pool.logBin() * (fromInt256(pool.tickBin - pool.BINS() / 2) + pool.binFrac + pool.halfspread));
            while ((limitPrice.isDefined() ? vars.lastPrice < limitPrice.get() : true) && (vars.pushing ? vars.input : vars.output) < vars.maxTokens)
            {
                if (pool.binFrac == fromInt256(1)) {
                    if (pool.tickBin == pool.BINS() - 1) break;
                    pool.uptick();
                }
                vars.liquid = pool.liquid();
                vars.outFactor = pool.epsilon_() / pool.sqrtMid() * vars.liquid;
                vars.qEnd = vars.pushing || vars.liquid <= O
                    ? fromInt256(1)
                    : min(pool.binFrac + (vars.maxTokens - vars.output) / vars.outFactor, fromInt256(1));
                vars.sweepPrice =
                    exp(pool.logBin() * (fromInt256(pool.tickBin - pool.BINS() / 2) + fromInt256(2) * vars.qEnd - pool.binFrac + pool.halfspread));
                if (vars.liquid > O) {
                    vars.endPrice = limitPrice.isDefined() ? min(limitPrice.get(), vars.sweepPrice) : vars.sweepPrice;
                    vars.inFactor = vars.outFactor / (fromInt256(2) * pool.logBin());
                    vars.stepInput = vars.inFactor * (vars.endPrice - vars.lastPrice);
                    vars.sweepInput = vars.input + vars.stepInput;
                    if (vars.pushing && vars.sweepInput > vars.maxTokens) {
                        vars.stepInput = vars.maxTokens - vars.input;
                        vars.lastPrice = vars.lastPrice + vars.stepInput / vars.inFactor;
                        vars.input = vars.maxTokens;
                    } else {
                        vars.lastPrice = vars.endPrice;
                        vars.input = vars.sweepInput;
                    }
                    vars.qNew_ = vars.lastPrice == vars.sweepPrice
                        ? vars.qEnd
                        : min(
                            (log(vars.lastPrice) / pool.logBin() - (fromInt256(pool.tickBin - pool.BINS() / 2) + pool.halfspread) + pool.binFrac)
                                / fromInt256(2),
                            fromInt256(1)
                        );
                    vars.qStep_ = vars.qNew_ - pool.binFrac;
                    vars.stepOutput = vars.outFactor * vars.qStep_;
                    if (!vars.pushing && vars.qEnd < fromInt256(1) && vars.endPrice == vars.sweepPrice) vars.output = vars.maxTokens;
                    else vars.output = vars.output + vars.stepOutput;
                    vars.charged = vars.stepInput - vars.stepOutput * pool.mid();
                    vars.gained = vars.charged / vars.liquid;
                    spotFee_(pool, !vars.pullToken, (fromInt256(1) - pool.used.nowAt(pool, pool.tickBin) * pool.deflator) * vars.gained, vars.charged);
                    vars.varMove = vars.varMove + fromInt256(4) * vars.gained / pool.sqrtMid();
                    (vars.qNew, vars.qStep) = (vars.qNew_, vars.qStep_);
                } else {
                    vars.lastPrice = vars.sweepPrice;
                    (vars.qNew, vars.qStep) = (fromInt256(1), fromInt256(1) - pool.binFrac);
                }
                pool.halfspread = pool.halfspread + vars.qStep;
                pool.binFrac = vars.qNew;
            }
            vars.transfer = UserPay.Info(-vars.output, vars.input);
        } else {
            vars.limitPrinv = limitPrice.isDefined() ? toOptQuad(fromInt256(1) / limitPrice.get()) : limitPrice;
            vars.lastPrinv = exp(-pool.logBin() * (fromInt256(pool.tickBin - pool.BINS() / 2) + pool.binFrac - pool.halfspread));
            while (
                (vars.limitPrinv.isDefined() ? vars.lastPrinv < vars.limitPrinv.get() : true)
                    && (vars.pushing ? vars.input : vars.output) < vars.maxTokens
            ) {
                if (pool.binFrac == fromInt256(0)) {
                    if (pool.tickBin == 0) break;
                    pool.downtick();
                }
                vars.liquid = pool.liquid();
                vars.outFactor = pool.epsilon_() * pool.sqrtMid() * vars.liquid;
                vars.qEnd = vars.pushing || vars.liquid <= O ? fromInt256(0) : max(pool.binFrac - (vars.maxTokens - vars.output) / vars.outFactor, O);
                vars.sweepPrinv =
                    exp(-pool.logBin() * (fromInt256(pool.tickBin - pool.BINS() / 2) + fromInt256(2) * vars.qEnd - pool.binFrac - pool.halfspread));
                if (vars.liquid > O) {
                    vars.endPrinv = vars.limitPrinv.isDefined() ? min(vars.limitPrinv.get(), vars.sweepPrinv) : vars.sweepPrinv;
                    vars.inFactor = vars.outFactor / (fromInt256(2) * pool.logBin());
                    vars.stepInput = vars.inFactor * (vars.endPrinv - vars.lastPrinv);
                    vars.sweepInput = vars.input + vars.stepInput;
                    if (vars.pushing && vars.sweepInput > vars.maxTokens) {
                        vars.stepInput = vars.maxTokens - vars.input;
                        vars.lastPrinv = vars.lastPrinv + vars.stepInput / vars.inFactor;
                        vars.input = vars.maxTokens;
                    } else {
                        vars.lastPrinv = vars.endPrinv;
                        vars.input = vars.sweepInput;
                    }
                    vars.qNew_ = vars.lastPrinv == vars.sweepPrinv
                        ? vars.qEnd
                        : max(
                            (log(vars.lastPrinv) / (-pool.logBin()) - (fromInt256(pool.tickBin - pool.BINS() / 2) - pool.halfspread) + pool.binFrac)
                                / fromInt256(2),
                            O
                        );
                    vars.qStep_ = pool.binFrac - vars.qNew_;
                    vars.stepOutput = vars.outFactor * vars.qStep_;
                    if (!vars.pushing && vars.qEnd > fromInt256(0) && vars.endPrinv == vars.sweepPrinv) vars.output = vars.maxTokens;
                    else vars.output = vars.output + vars.stepOutput;
                    vars.charged = vars.stepInput - vars.stepOutput / pool.mid();
                    vars.gained = vars.charged / vars.liquid;
                    spotFee_(pool, !vars.pullToken, (fromInt256(1) - pool.used.nowAt(pool, pool.tickBin) * pool.deflator) * vars.gained, vars.charged);
                    vars.varMove = vars.varMove + fromInt256(4) * vars.gained * pool.sqrtMid();
                    (vars.qNew, vars.qStep) = (vars.qNew_, vars.qStep_);
                } else {
                    vars.lastPrinv = vars.sweepPrinv;
                    (vars.qNew, vars.qStep) = (fromInt256(0), pool.binFrac);
                }
                pool.halfspread = pool.halfspread + vars.qStep;
                pool.binFrac = vars.qNew;
            }
            vars.transfer = UserPay.Info(vars.input, -vars.output);
        }
        pool.dayMove.add(pool, vars.varMove);
        return vars.transfer;
    }

    function spotFee_(PoolState storage pool, bool inToken, Quad accrual, Quad) public {
        PiecewiseGrowthNew.Info storage fee = pool.fees[inToken ? 1 : 0].live(pool.splits);
        fee.accrued = fee.accrued + accrual;
    }

    function swap(PoolState storage pool, SpotSwapParams memory params) external returns (UserPay.Info memory) {
        if (params.shove.isNaN()) revert InvalidPushAmount();
        return swap(pool, params.shove, params.ofToken, params.limitPrice);
    }
}