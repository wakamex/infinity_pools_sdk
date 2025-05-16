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
import {isInfinity} from "src/types/ABDKMathQuad/Helpers.sol";

library SwapperInternal {
    using SafeCast for int256;
    using GapStagedFrame for GapStagedFrame.Info;
    using GrowthSplitFrame for GrowthSplitFrame.Info;
    using JumpyFallback for JumpyFallback.Info;
    using DropFaberTotals for DropFaberTotals.Info;
    using JumpyAnchorFaber for JumpyAnchorFaber.Info;
    using DeadlineSet for DeadlineSet.Info;
    using DeadlineJumps for DeadlineSet.Info;
    using NettingGrowth for NettingGrowth.Info;

    struct Info {
        OptInt256 twapUntil;
        OptInt256 deadEra;
        Quad tokenMix;
        Quad unlockDate;
        Quad oweLimit;
        Quad lentCapacity0;
        Quad lentCapacity1;
        // The owed liquidity is tracked in the Swapper, as lent + interests
        // This quantity is set at creation time and never changes during the swapper lifecycle
        Quad[] owed;
        // The lent liquidity is tracked in the Swapper in inflated units
        // This quantity is set at creation time and never changes during the swapper lifecycle
        Quad[] lent;
        Quad[] minted;
        int32 startBin;
        int32 strikeBin;
        address owner;
        bool token;
    }

    error SwapperExpired(int256 era, int256 deadEra);
    error DeadlineDoesNotCoverLockInDate(int256 deadEra, Quad unlockDate);
    error InvalidTokenMixFraction(Quad tokenMix);
    error TWAPEndsBeforeDeadline(int256 depegEra, int256 deadEra);
    error FixedTokenExceedsCapacity(bool token, Quad tokenMix, Quad capacity);

    function init(Info memory self, PoolState storage pool) external view returns (Info memory) {
        {
            // Inflator is used to record quantities that are independent of the current time
            // To convert them back in quantities at a certain time t, they have to be multiplied by the deflator corresponding at that t time
            Quad inflator = (POSITIVE_ONE / pool.deflator);
            Quad sum0;
            Quad sum1;
            for (uint256 i; i < self.owed.length; i++) {
                // The liquidity tracked in the Swapper is independent of time and therefore it is multiplied by the inflator before being stored
                // The actual owed liquidity at a certain point in time is affected by a time decay factor
                self.owed[i] = self.owed[i] * inflator;
                // Sum of base token and quote token corresponding to the owed liquidity inflated for each bin
                sum0 = sum0 + self.owed[i] / sqrtStrike(pool.splits, self.startBin + int256(i));
                sum1 = sum1 + self.owed[i] * sqrtStrike(pool.splits, self.startBin + int256(i));
            }
            // Total owed liquidity in inflated units
            // This is key to compute many quantities at a certain point in time
            self.oweLimit = (sum0 * sum1).sqrt();
        }
        {
            Quad sum0;
            Quad sum1;
            for (uint256 i; i < self.lent.length; i++) {
                // Sum of base token and quote token corresponding to the lent liquidity inflated for each bin
                // There is no need to multiply this by the inflator because `lent` is already inflated at the time it is computed
                sum0 = sum0 + self.lent[i] / sqrtStrike(pool.splits, self.startBin + int256(i));
                sum1 = sum1 + self.lent[i] * sqrtStrike(pool.splits, self.startBin + int256(i));
            }

            // For lent, no need to multiply by the inflator since it is already inflated
            // These represent the lent capacity in token0 and token1 in inflated terms respectively
            self.lentCapacity0 = pool.epsilon * sum0;
            self.lentCapacity1 = pool.epsilon * sum1;
        }

        return self;
    }

    function signed(bool enable, Quad amount) internal pure returns (Quad) {
        return enable ? amount : -amount;
    }

    /**
     * @dev Updates the fees tracker as a result of borrowing liquidity
     *     @param liquidityRatio: The fees here are expressed as a ratio between the fees in liquidity units (computed as owed - lent)  and the minted liquidity in the specific bin (kind of), so it is a pure number (not liquidity units)
     *     @param bin: The bin for which the fees are updated
     *     @param deadEra: The era at which the fees are due
     */
    function feeCreateOne(PoolState storage pool, Quad liquidityRatio, int256 bin, OptInt256 deadEra) internal {
        pool.joinStaged.flush(pool, bin);

        // The fees are not tracked as tokens directly, to convert these quantities into actual tokens need to multiply by liquidity
        Quad[] memory amounts = new Quad[](1);
        amounts[0] = pool.epsilon * liquidityRatio / sqrtStrike(pool.splits, bin);
        pool.fees[0].create(pool, pool.splits, bin, amounts, deadEra);

        amounts[0] = pool.epsilon * liquidityRatio * sqrtStrike(pool.splits, bin);
        pool.fees[1].create(pool, pool.splits, bin, amounts, deadEra);
    }

    /**
     * @dev Computes the backing of the swapper when the TWAP is not active, either because not defined or expired
     *     @dev This is basically a subfunction of the `backing()` function
     */
    function noTwap(Info memory self, PoolState storage pool, bool token, Quad tokenMix) internal view returns (Quad) {
        if (self.deadEra.isDefined()) {
            // Swapper expires case
            // NOTE: As the pool date gets closer and closer to the Swapper deadEra, the `expiryFraction` gets closer and closer to 1 resulting in the returned token `Z` and token `I` converging to the related lentCapcity values (that are in inflated terms) and weighted by the tokenMix and finally deflated by the current pool deflator
            // NOTE: So in this branch the backing of a certain token is a decreasing function of time and is zero when the Swapper expires
            Quad expiryFraction = (pool.date - eraDate(self.deadEra.get())).exp2();
            if (token == Z) {
                return (
                    (POSITIVE_ONE - expiryFraction) * pool.epsilon * self.oweLimit / sqrtStrike(pool.splits, self.strikeBin)
                        + expiryFraction * self.lentCapacity0
                ) * (POSITIVE_ONE - tokenMix) * pool.deflator;
            }
            // if (token == I)
            else {
                return (
                    (POSITIVE_ONE - expiryFraction) * pool.epsilon * self.oweLimit * sqrtStrike(pool.splits, self.strikeBin)
                        + expiryFraction * self.lentCapacity1
                ) * tokenMix * pool.deflator;
            }
        } else {
            // Swapper does not expire case
            // NOTE: In this branch, the dependency on time is just given by the pool deflator
            // Fixed term loan, no TWAP
            if (token == Z) return pool.epsilon * self.oweLimit * (POSITIVE_ONE - tokenMix) / sqrtStrike(pool.splits, self.strikeBin) * pool.deflator;
            // if (token == I)
            else return pool.epsilon * self.oweLimit * tokenMix * sqrtStrike(pool.splits, self.strikeBin) * pool.deflator;
        }
    }

    struct EndTokenMixLocalVars {
        Quad twapDeflator;
        Quad capacity;
        Quad deadDeflator;
        Quad ratio;
    }

    /**
     * @dev Computes the token mix when the TWAP has ended
     */
    function endTokenMix(Info storage self, PoolState storage pool) internal view returns (Quad res) {
        EndTokenMixLocalVars memory vars;

        if (!self.twapUntil.isDefined()) {
            // Trivial case when no TWAP is defined
            res = self.tokenMix;
        } else {
            // Case when the TWAP is defined: at the time the TWAP ends the exposure is still `tokenMix` since this is what the TWAP is for, but as soon as it expires it changes
            // Token the TWAP offers fixed exposure to
            bool fixedToken = self.token;
            // Era at which the TWAP ends for the swapper
            int256 depegEra = self.twapUntil.get();
            // Deflator at the time the TWAP ends
            vars.twapDeflator = pool.deflator * (pool.date - eraDate(depegEra)).exp2();

            // Computing `vars.capacity` which is the capacity of the swapper in token0 or token1 depending on `fixedToken` value at the time the TWAP ends
            if (self.deadEra.isDefined()) {
                // If the Swapper expires at some point in the future
                if (self.deadEra.get() == depegEra) {
                    // If the time when the TWAP end time is the same as the time when the swapper expires then the capacity is just the lent liquidity at the time the TWAP ends converted into `fixedToken`
                    vars.capacity = vars.twapDeflator * (fixedToken == Z ? self.lentCapacity0 : self.lentCapacity1);
                } else {
                    // If the time when the TWAP ends is different from the time when the swapper expires
                    // Compute the deflator when the swapper expires
                    vars.deadDeflator = pool.deflator * (pool.date - eraDate(self.deadEra.get())).exp2();

                    // The capacity for 0 < depegEra < deadEra case is the sum of 2 components
                    // For the depegEra < t < deadEra period, the capacity depends on the deadDeflator only
                    // For the 0 < t < depegEra period, the capacity depends on the twapDeflator only and therefore the capacity due to deadDeflator is subtracted in this case since it is already factored in the other case
                    vars.capacity = self.oweLimit * (vars.twapDeflator - vars.deadDeflator)
                        * (
                            fixedToken == Z
                                ? pool.epsilon / sqrtStrike(pool.splits, self.strikeBin)
                                : pool.epsilon * sqrtStrike(pool.splits, self.strikeBin)
                        ) + vars.deadDeflator * (fixedToken == Z ? self.lentCapacity0 : self.lentCapacity1);
                }
            } else {
                // If the Swapper never expires
                // The capacity is just the owed liquidity limit at the time the TWAP ends converted into `fixedToken`
                vars.capacity = self.oweLimit * vars.twapDeflator
                    * (fixedToken == Z ? pool.epsilon / sqrtStrike(pool.splits, self.strikeBin) : pool.epsilon * sqrtStrike(pool.splits, self.strikeBin));
            }
            // NOTE: In the validate, it is checked that the tokenMix is <= the capacity of the swapper and therefore the ratio is always between 0 and 1
            vars.ratio = (self.tokenMix / vars.capacity);
            res = (fixedToken == I)
                ? ((vars.ratio > POSITIVE_ONE) ? POSITIVE_ONE : vars.ratio)
                : ((POSITIVE_ONE - vars.ratio) < POSITIVE_ZERO ? POSITIVE_ZERO : (POSITIVE_ONE - vars.ratio));
        }
        return res;
    }

    struct BackingLocalVars {
        bool fixedToken;
        int256 depegEra;
        Quad twapLeft;
        Quad twapDeflator;
        Quad deadDeflator;
        Quad capacity0;
        Quad capacity1;
        Quad owedMean;
        Quad towardToken;
    }

    /**
     * @dev Computes the amount of `token` is required to back the swapper
     *     @dev It is used in functions that change the state of the swapper to recompute the amounts the caller has to pay to back the swapper
     */
    function backing(Info storage self, PoolState storage pool, bool token) internal view returns (Quad) {
        BackingLocalVars memory vars;

        Quad res;

        if (!self.twapUntil.isDefined()) {
            // No TWAP Case, the calculation is performed in `noTwap()` function
            return noTwap(self, pool, token, self.tokenMix);
        } else {
            // TWAP Defined Case
            vars.fixedToken = self.token;
            vars.depegEra = self.twapUntil.get();
            if (pool.era >= vars.depegEra) {
                // TWAP Expired Case, the calculation is performed in `noTwap()` function
                return noTwap(self, pool, token, endTokenMix(self, pool));
            } else {
                // TWAP Active Case
                if (token == vars.fixedToken) {
                    // DeltaT for which the TWAP is going to remain active
                    vars.twapLeft = eraDate(vars.depegEra) - pool.date;
                    res = self.tokenMix * (POSITIVE_ONE + (pool.twapSpread * LAMBDA * vars.twapLeft));
                } else {
                    if (self.deadEra.isDefined()) {
                        // Swapper Expires Case
                        int256 deadEra = self.deadEra.get();
                        vars.twapDeflator = pool.deflator * (pool.date - eraDate(vars.depegEra)).exp2();

                        if (vars.depegEra == deadEra) {
                            vars.capacity0 = vars.twapDeflator * self.lentCapacity0;
                            vars.capacity1 = vars.twapDeflator * self.lentCapacity1;
                        } else {
                            // Case deadEra > depegEra
                            vars.deadDeflator = pool.deflator * (pool.date - eraDate(deadEra)).exp2();

                            // The extra tokens to cover the depegEra < t < deadEra depend on the `oweLimit` deflated by deflator related to the DeltaT = deadEra - depegEra
                            // NOTE: This is guaranteed to be positive since 2^(date - depeg) > 2^(date - dead) because depeg < dead in this logic branch
                            vars.owedMean = ((vars.twapDeflator - vars.deadDeflator) * pool.epsilon * self.oweLimit);

                            // In general, the liquidity is
                            // - converted to token0 by dividing for sqrtStrike(swapper.strikeBin)
                            // - converted to token1 by multiplying for sqrtStrike(swapper.strikeBin)
                            // These capacities are calculated using the full `oweMean` so they represent the max capacity for a token and will be used as normalization factors in the rest of the logic of this branch
                            vars.capacity0 = (vars.owedMean / sqrtStrike(pool.splits, self.strikeBin)) + (vars.deadDeflator * self.lentCapacity0);
                            vars.capacity1 = (vars.owedMean * sqrtStrike(pool.splits, self.strikeBin)) + (vars.deadDeflator * self.lentCapacity1);
                        }

                        res = (token == Z)
                            ? (((pool.deflator - vars.twapDeflator) * pool.epsilon * self.oweLimit) / sqrtStrike(pool.splits, self.strikeBin))
                                + vars.capacity0 * (POSITIVE_ONE - self.tokenMix / vars.capacity1)
                            : (((pool.deflator - vars.twapDeflator) * pool.epsilon * self.oweLimit) * sqrtStrike(pool.splits, self.strikeBin))
                                + vars.capacity1 * (POSITIVE_ONE - self.tokenMix / vars.capacity0);
                    } else {
                        // Swapper does not expire case

                        // In general, the liquidity is
                        // - converted to token0 by dividing for sqrtStrike(swapper.strikeBin)
                        // - converted to token1 by multiplying for sqrtStrike(swapper.strikeBin)
                        vars.towardToken =
                            (token == Z) ? (POSITIVE_ONE / sqrtStrike(pool.splits, self.strikeBin)) : sqrtStrike(pool.splits, self.strikeBin);

                        res = (((pool.epsilon * self.oweLimit) * pool.deflator) - (self.tokenMix * vars.towardToken)) * vars.towardToken;
                    }
                }
            }
        }
        return res;
    }

    function feeCreate(Info storage self, PoolState storage pool, Quad[] memory liquidityRatio) internal {
        if (!self.deadEra.isDefined()) {
            for (uint256 index = 0; index < liquidityRatio.length; index++) {
                pool.joinStaged.flush(pool, self.startBin + int256(index));
            }
        }
        Quad[] memory interest = new Quad[](liquidityRatio.length);
        for (uint256 index = 0; index < liquidityRatio.length; index++) {
            interest[index] = pool.epsilon * liquidityRatio[index] / sqrtStrike(pool.splits, self.startBin + int256(index));
        }
        pool.fees[0].create(pool, pool.splits, self.startBin, interest, self.deadEra);
        for (uint256 index = 0; index < liquidityRatio.length; index++) {
            interest[index] = pool.epsilon * liquidityRatio[index] * sqrtStrike(pool.splits, self.startBin + int256(index));
        }
        pool.fees[1].create(pool, pool.splits, self.startBin, interest, self.deadEra);
    }

    /**
     * @dev Updates the liquidity lending accounting in the pool and updates the corresponding fees.
     *     @param enable: If true, the function updates the pool accounting and the fees. If false, it undoes the operations done by the function when enable = true
     *     For the operation undoing to work correctly, the function must be called with the same state as when enable = true so this is why `self.minted` is not updated when enable = false
     */
    function borrow(Info storage self, PoolState storage pool, bool enable) public {
        int256 scale = pool.splits;
        // Looping over all the bins the liquidity has been borrowed from
        Quad[] memory amounts = new Quad[](self.owed.length);
        for (int256 index = 0; (index < int256(self.owed.length)); index = (index + 1)) {
            // Current bin
            int256 bin = (self.startBin + index);

            // Minted is a normalization factor applied to the borrowed and lent liquidity for the fees and flows calculations
            // For doing new operations only, update the locally recorded snapshot of the minted liquidity in the pool for the current bin
            // For undoing operations, which is the case for `enable = false`, the minted liquidity is not updated
            // Minted tracks the highest historical value of each bin, separately, seen when `borrow()` is called
            if (enable) self.minted[index.toUint256()] = max(self.minted[index.toUint256()], fluidAt(pool.minted, bin, pool.splits));

            // Tracking the new lent amount for the current bin
            // If positive, it tracks the amount of liquidity lent and expiring at deadEra
            pool.lent.createOne(pool.era, pool.splits, signed(enable, self.lent[index.toUint256()]), bin, self.deadEra);
            pool.used.createOne(
                pool.era, pool.splits, signed(enable, self.lent[index.toUint256()] / self.minted[index.toUint256()]), bin, self.deadEra
            );

            pool.owed.createOne(pool.era, pool.splits, signed(enable, self.owed[index.toUint256()]), bin, self.deadEra);
            amounts[index.toUint256()] = signed(enable, self.owed[index.toUint256()] - self.lent[index.toUint256()]) / self.minted[index.toUint256()];
        }
        // Creating new fees resulting from delta between the owed and lent liquidity normalized over the current minted
        feeCreate(self, pool, amounts);

        // Creating flows for lent liquidity for token0 and token1 re-entering the pool at the deadEra
        for (uint256 index = 0; index < amounts.length; index++) {
            amounts[index] = signed(enable, pool.epsilon * self.lent[index] / sqrtStrike(pool.splits, self.startBin + int256(index)));
        }
        pool.lentEnd[0].expire(pool.era, amounts, scale, self.startBin, self.deadEra);

        for (uint256 index = 0; index < amounts.length; index++) {
            amounts[index] = signed(enable, pool.epsilon * self.lent[index] * sqrtStrike(pool.splits, self.startBin + int256(index)));
        }
        pool.lentEnd[1].expire(pool.era, amounts, scale, self.startBin, self.deadEra);
        for (uint256 index = 0; index < amounts.length; index++) {
            amounts[index] = signed(enable, -self.owed[index] / sqrtStrike(pool.splits, self.startBin + int256(index)));
        }
        pool.flowHat[0].create(pool, amounts, scale, self.startBin, self.deadEra);
        for (uint256 index = 0; index < amounts.length; index++) {
            amounts[index] = signed(enable, -self.owed[index] * sqrtStrike(pool.splits, self.startBin + int256(index)));
        }
        pool.flowHat[1].create(pool, amounts, scale, self.startBin, self.deadEra);
    }

    /**
     * @dev Swapper Expired Check
     */
    function isExpired(Info storage self, PoolState storage pool) internal view returns (bool) {
        bool result = false;

        if (self.deadEra.isDefined()) {
            // The Swapper is expired if the current era is greater than or equal to the dead era
            if (pool.era >= (self.deadEra.get())) result = true;
            else result = false;
        } else {
            result = false;
        }
        return result;
    }

    function checkAlive(Info storage self, PoolState storage pool) public view {
        if (isExpired(self, pool)) revert SwapperExpired(pool.era, self.deadEra.get());
    }

    /**
     * @dev This function is used to calculate the flow of the swapper
     *     @dev There are 2 quantites for each token that are computed here: the payoff and the flows of tokens back into the system
     *     @dev From a time perspective,
     *     - the flows of tokens back into the system only depend on the Swapper expiration era and the
     *     - the payoff depends on the Swapper expiration era and the TWAP expiration era, if they do not coincide each payoff will be composed of 2 parts: one for the 0 < t < depegEra and one for the depegEra < t < deadEra
     */
    function flow(Info storage self, PoolState storage pool, bool enable) public {
        // The token mix after the TWAP if any, has expired
        Quad finalTokenMix = endTokenMix(self, pool);

        // The flows when there is no TWAP, are just the `oweLimit` split according to the `finalTokenMix` so `flow0` and `flow1` will be used in the banches of the logic regarding TWAP expired and no TWAP
        // The flow of liquidity that will become token0
        Quad flow0 = self.oweLimit * (POSITIVE_ONE - finalTokenMix);
        // The flow of liquidity that will become token1
        Quad flow1 = self.oweLimit * finalTokenMix;

        // Payoff Creation, the expiration time needs to be taken into account
        if (self.twapUntil.isDefined() && self.twapUntil.get() > pool.era) {
            // TWAP is active i.e. defined and not expired yet

            // Computing the payoff related to the TWAP, expiring at `depegEra`
            bool fixedToken = self.token;
            int256 depegEra = self.twapUntil.get();
            // If the desired exposure is to token0, then the full `oweLimit` will become token1
            if (fixedToken == Z) AnyPayoff.payoffCreate(pool, I, signed(enable, self.oweLimit), self.strikeBin, wrap(depegEra));
            // If the desired exposure is to token1, then the full `oweLimit` will become token0
            else if (fixedToken == I) AnyPayoff.payoffCreate(pool, Z, signed(enable, self.oweLimit), self.strikeBin, wrap(depegEra));

            pool.netting[(fixedToken == true ? 1 : 0)].create(pool, signed(enable, self.tokenMix), depegEra);
            if (self.deadEra != wrap(depegEra)) {
                // If the swapper matures after the TWAP has expired, the payoff has to be extended for the depegEra < t < deadEra interval using the `flow0` and `flow1` quantities previously calculated
                AnyPayoff.payoffExtend(pool, Z, signed(enable, flow0), self.strikeBin, wrap(depegEra), self.deadEra);
                AnyPayoff.payoffExtend(pool, I, signed(enable, flow1), self.strikeBin, wrap(depegEra), self.deadEra);
            }
        } else {
            // If no TWAP or it is expired, then the payoffs are just a function of `flow0` and `flow1` respectively, expiring at `deadEra` i.e. when the swapper expires
            AnyPayoff.payoffCreate(pool, Z, signed(enable, flow0), self.strikeBin, self.deadEra);
            AnyPayoff.payoffCreate(pool, I, signed(enable, flow1), self.strikeBin, self.deadEra);
        }

        if (self.deadEra.isDefined()) {
            // Since `self.lentCapacity0` is the max possible amount of token0 "ratio" (i.e. this quantity has to be multiplied by liquidity to become a token quantity) then the actual amount is the `(POSITIVE_ONE - finalTokenMix)` share
            // Since `self.lentCapacity1` is the max possible amount of token1 "ratio" (i.e. this quantity has to be multiplied by liquidity to become a token quantity) then the actual amount is the `(finalTokenMix)` share
            pool.expire[0].create(pool.era, signed(enable, self.lentCapacity0 * (POSITIVE_ONE - finalTokenMix)), self.deadEra);
            pool.expire[1].create(pool.era, signed(enable, self.lentCapacity1 * finalTokenMix), self.deadEra);
        }
    }

    /**
     * @dev Ignore
     */
    function maturing(Info storage self, PoolState storage pool, bool token) internal view returns (Quad) {
        return (
            flowing(self, token)
                * ((token == Z) ? (pool.epsilon / sqrtStrike(pool.splits, self.strikeBin)) : (pool.epsilon * sqrtStrike(pool.splits, self.strikeBin)))
        );
    }

    /**
     * @dev Ignore
     */
    function flowing(Info storage self, bool token) internal view returns (Quad) {
        Quad res = POSITIVE_ZERO;

        if (!(self.twapUntil.isDefined())) {
            res = (self.oweLimit * ((token == Z) ? (POSITIVE_ONE - self.tokenMix) : self.tokenMix));
        } else {
            bool fixedToken = self.token;

            if ((token == fixedToken)) res = POSITIVE_ZERO;
            else res = self.oweLimit;
        }
        return res;
    }

    struct ValidateLocalVars {
        int256 depegEra;
        Quad twapDeflator;
        bool fixedToken;
        Quad capacity;
        Quad deadDeflator;
        Quad owedMean;
    }

    function validate(Info storage self, PoolState storage pool) public {
        ValidateLocalVars memory vars;

        if (self.deadEra.isDefined() && ((eraDate(self.deadEra.get())) < self.unlockDate)) {
            revert DeadlineDoesNotCoverLockInDate(self.deadEra.get(), self.unlockDate);
        }

        checkAlive(self, pool);

        if (self.tokenMix < POSITIVE_ZERO) revert InvalidTokenMixFraction(self.tokenMix);

        if ((!self.twapUntil.isDefined())) {
            if (!(self.tokenMix <= POSITIVE_ONE)) revert InvalidTokenMixFraction(self.tokenMix);
        } else {
            vars.depegEra = self.twapUntil.get();
            if (self.deadEra.isDefined() && (self.deadEra.get() < vars.depegEra)) {
                // The TWAP end time should be before the Swapper expiration time
                revert TWAPEndsBeforeDeadline(vars.depegEra, self.deadEra.get());
            }

            vars.twapDeflator = pool.deflator * (pool.date - eraDate(vars.depegEra)).exp2();
            vars.fixedToken = self.token;

            // Computing the `vars.capacity` to validate the new `tokenMix` value
            if (self.deadEra.isDefined()) {
                // Swapper expiring at some date
                Quad lentCapacity = vars.fixedToken == Z ? self.lentCapacity0 : self.lentCapacity1;
                if (vars.depegEra == self.deadEra.get()) {
                    // Case where the TWAP and the Swapper end at the same time
                    // In this case, the capacity is just the lent liquidity deflated at the time the TWAP ends
                    vars.capacity = vars.twapDeflator * lentCapacity;
                } else {
                    // Case where the TWAP and the Swapper end at different times
                    //		val deadDeflator = deflator * exp(ln2 * (date - eraDate(deadEra)))
                    //								val owedMean = (twapDeflator - deadDeflator) * ε * oweLimit
                    //								(fixedToken match { case Z => owedMean / sqrtStrike; case I => owedMean * sqrtStrike }) + deadDeflator * lentCapacity

                    // Deflator when the Swapper ends
                    vars.deadDeflator = pool.deflator * (pool.date - eraDate(self.deadEra.get())).exp2();
                    vars.owedMean = (vars.twapDeflator - vars.deadDeflator) * pool.epsilon * self.oweLimit;
                    vars.capacity = vars.fixedToken == Z
                        ? (vars.owedMean / sqrtStrike(pool.splits, self.strikeBin))
                        : (vars.owedMean * sqrtStrike(pool.splits, self.strikeBin));
                    vars.capacity = vars.capacity + vars.deadDeflator * lentCapacity;
                }
            } else {
                vars.capacity = vars.fixedToken == Z
                    ? (pool.epsilon / sqrtStrike(pool.splits, self.strikeBin))
                    : (pool.epsilon * sqrtStrike(pool.splits, self.strikeBin));
                vars.capacity = vars.capacity * self.oweLimit * vars.twapDeflator;
            }
            if (isInfinity(self.tokenMix)) self.tokenMix = vars.capacity;
            else if ((self.tokenMix > vars.capacity)) revert FixedTokenExceedsCapacity(vars.fixedToken, self.tokenMix, vars.capacity);
        }
    }
}