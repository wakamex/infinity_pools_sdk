// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad} from "src/types/ABDKMathQuad/Quad.sol";
import {NewLoan} from "src/libraries/external/NewLoan.sol";
import {Spot} from "src/libraries/external/Spot.sol";
import {OptInt256} from "src/types/Optional/OptInt256.sol";
import {Structs} from "src/libraries/external/Structs.sol";
import {SwapperInternal} from "src/libraries/external/SwapperInternal.sol";

interface IInfinityPool {
    enum Action {
        SWAP,
        NEW_LOAN,
        UNWIND,
        REFLOW,
        RESET,
        POUR,
        DRAIN,
        COLLECT,
        TAP
    }

    event PoolInitialized(Quad startPrice, Quad quadVar0, Quad twapSpread, Quad poolDate);

    event Borrowed(
        address indexed user,
        uint256 indexed swapperNum,
        Quad[] owedPotential,
        int256 startBin,
        int256 strikeBin,
        Quad tokenMix,
        Quad lockinEnd,
        OptInt256 deadEra,
        bool token,
        OptInt256 twapUntil
    );

    event LiquidityAdded(
        address indexed user,
        int256 startTub,
        int256 stopTub,
        Quad liquidity,
        uint256 indexed lpNum,
        int256 amount0,
        int256 amount1,
        int256 earnEra,
        Quad poolDate
    );

    event LiquidityTapped(uint256 indexed lpNum, Quad poolDate);

    event LiquidityDrained(uint256 indexed lpNum, address indexed receiver, int256 amount0, int256 amount1, Quad poolDate);

    event LiquidityCollected(uint256 indexed lpNum, address indexed receiver, int256 amount0, int256 amount1, Quad poolDate);

    event SwapperCreated(uint256 id, Quad poolDate, Quad tokenMixParam, SwapperInternal.Info info);

    event SwapperReset(
        uint256 indexed swapperId,
        OptInt256 deadEra,
        Quad tokenMix,
        bool fixedToken,
        OptInt256 twapUntil,
        address receiver,
        int256 amount0,
        int256 amount1,
        Quad poolDate
    );

    event SwapperReflow(
        uint256 indexed swapperId,
        Quad tokenMix,
        bool fixedToken,
        OptInt256 twapUntil,
        address receiver,
        int256 amount0,
        int256 amount1,
        Quad poolDate
    );

    event SwapperUnwind(uint256 indexed swapperId, address receiver, Quad poolDate);

    event SwapperCreationEnabled();

    error InvalidLPNumber();
    error OnlyFactoryIsAllowed();

    function getPoolPriceInfo() external returns (Structs.PoolPriceInfo memory);
    function getPoolInfo() external view returns (address, address, int256);

    function newLoan(NewLoan.NewLoanParams memory params, bytes calldata data) external returns (uint256, int256, int256);
    function swap(Spot.SpotSwapParams memory params, address receiver, bytes calldata data) external returns (int256 amount0, int256 amount1);

    function unwind(uint256 swapperId, address receiver, bytes calldata data) external returns (int256 amount0, int256 amount1);
    function reflow(uint256 swapperId, Quad tokenMix, bool fixedToken, OptInt256 twapUntil, address receiver, bytes calldata data)
        external
        returns (int256 amount0, int256 amount1);
    function reset(uint256 swapperId, OptInt256 deadEra, Quad tokenMix, bool fixedToken, OptInt256 twapUntil, address receiver, bytes calldata data)
        external
        returns (int256, int256);
    function getPourQuantities(int256 startTub, int256 stopTub, Quad liquidity) external returns (int256, int256);
    function pour(int256 startTub, int256 stopTub, Quad liquidity, bytes calldata data) external returns (uint256, int256, int256, int256);

    function getLpCount() external view returns (uint256);
    function getLiquidityPosition(uint256 lpNum) external returns (Structs.LiquidityPosition memory);
    function drain(uint256 lpNum, address receiver, bytes calldata data) external returns (int256, int256);
    function collect(uint256 lpNum, address receiver, bytes calldata data) external returns (int256, int256);
    function tap(uint256 lpNum) external;
    function enableSwapperCreation() external;
    function advance() external;

    function doActions(Action[] calldata actions, bytes[] calldata actionDatas, address receiver, bytes calldata data)
        external
        returns (int256 amount0, int256 amount1);

    function getSwappersCount() external view returns (uint256);

    function getBinLiquids(uint256 startBin, uint256 stopBin) external returns (Quad[] memory);
}