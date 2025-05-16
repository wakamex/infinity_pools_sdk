// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad, POSITIVE_ZERO} from "src/types/ABDKMathQuad/Quad.sol";

import {JumpyAnchorFaber} from "src/libraries/internal/JumpyAnchorFaber.sol";

import {BoxcarTubFrame} from "src/libraries/internal/BoxcarTubFrame.sol";
import {JumpyFallback} from "src/libraries/internal/JumpyFallback.sol";
import {DropFaberTotals} from "src/libraries/internal/DropFaberTotals.sol";
import {DeadlineJumps, DropsGroup, DeadlineSet} from "src/libraries/internal/DeadlineJumps.sol";
import {EraBoxcarMidSum} from "src/libraries/internal/EraBoxcarMidSum.sol";
import {GrowthSplitFrame} from "src/libraries/internal/GrowthSplitFrame.sol";
import {GapStagedFrame} from "src/libraries/internal/GapStagedFrame.sol";
import {BucketRolling} from "src/libraries/internal/BucketRolling.sol";
import {LP} from "src/libraries/external/LP.sol";
import {DeadlineFlag} from "src/libraries/internal/DeadlineFlag.sol";
import {SwapperInternal} from "src/libraries/external/Swapper.sol";
import {NettingGrowth} from "src/libraries/internal/NettingGrowth.sol";
import {Capper} from "src/libraries/internal/Capper.sol";
import {SparseFloat} from "src/libraries/internal/SparseFloat.sol";

interface IInfinityPoolState {}

struct PoolState {
    // NOTE: The order and type of the variables is important for the storage layout and the consequent gas costs so the criteria are
    // the order should go from the largest to the smallest types
    // mappings and dynamic array are storage pointers in the struct
    uint256 lpCount;
    int32 era;
    int32 tickBin;
    int32 splits;
    // All the Quads are 16 bytes so every pair of them takes 1 EVM Slot
    //cache decimals to avoid recompute everytime
    Quad tenToPowerDecimals0;
    Quad tenToPowerDecimals1;
    Quad fee;
    Quad epsilon;
    Quad move2Var;
    //time
    Quad date;
    Quad deflator;
    Quad entryDeflator;
    Quad binFrac;
    Quad surplus0;
    Quad surplus1;
    Quad twapSpread;
    Quad halfspread;
    // Each Address is 20 bytes, so can't be packed effectively unless there are 12 bytes types, but this is not the case here
    address factory;
    address token0;
    address token1;
    bool isPoolInitialized;
    //liquidity
    BoxcarTubFrame.Info minted;
    JumpyFallback.Info lent;
    DropFaberTotals.Info[2] lentEnd;
    JumpyFallback.Info used; // Liquidity utilisation ratio, inflated
    JumpyFallback.Info owed; // ω liquidity, inflated
    GapStagedFrame.Info joinStaged;
    BucketRolling.Info dayMove;
    DeadlineSet.Info[2] expire; //dropsGroup
    //resets
    // The `pool.resets` is like DeadlineJumps but instead of tracking Quad value associated to deadlines, it tracks boolean values associated to deadlines
    DeadlineFlag.Info resets;
    JumpyAnchorFaber.Info[2] flowHat;
    EraBoxcarMidSum.Info[2][2] flowDot;
    GrowthSplitFrame.Info[2] fees;
    BoxcarTubFrame.Info offRamp;
    NettingGrowth.Info[2] netting;
    SparseFloat.Info[2] priceRun;
    SparseFloat.Info[2] reserveRun;
    LP.Info[] lps;
    SwapperInternal.Info[] swappers;
    // No data packing for mapping
    mapping(bytes32 => Capper.Info) capper; // Keyed by (tick, token) hashed
}