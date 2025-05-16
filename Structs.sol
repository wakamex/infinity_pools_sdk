// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {LP} from "./LP.sol";
import {Quad} from "src/types/ABDKMathQuad/Quad.sol";

library Structs {
    int8 constant LP_STATE_OPENED = 1; // not earning yet
    int8 constant LP_STATE_ACTIVE = 2; // earning
    int8 constant LP_STATE_CLOSED = 3;

    struct PoolPriceInfo {
        int256 splits;
        int256 tickBin;
        Quad binFrac;
        Quad quadvar;
        Quad poolDate;
    }

    struct LiquidityInfo {
        int256 startTub;
        int256 stopTub;
        uint256 chainId;
        uint256 blockNumber;
        bytes32 blockHash;
        uint256 blockTimestamp;
        int256 splits;
        int256 tickBin;
        Quad binFrac;
        Quad poolDate;
        TubLiquidityInfo[] perTubInfos;
    }

    // per-tub
    struct TubLiquidityInfo {
        int256 tub;
        Quad accrued0;
        Quad accrued1;
        Quad liquidity;
        Quad utilization;
    }

    struct LiquidityPosition {
        uint256 lpNum;
        address token0;
        address token1;
        int256 lowerEdge; // correspond to lowerPrice
        int256 upperEdge; // correspond to upperPrice
        int256 earnEra;
        // N.B. amounts and fees are in token native unit
        int256 lockedAmount0;
        int256 lockedAmount1;
        int256 availableAmount0;
        int256 availableAmount1;
        int256 unclaimedFees0;
        int256 unclaimedFees1;
        int8 state; // LP_STATE_OPENED, LP_STATE_ACTIVE, LP_STATE_CLOSED
    }
}