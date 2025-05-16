// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {NewLoan} from "src/libraries/external/NewLoan.sol";
import {Spot} from "src/libraries/external/Spot.sol";
import {Quad} from "src/types/ABDKMathQuad/Quad.sol";

interface IInfinityPoolsPeriphery {
    struct AddLiquidityParams {
        address token0;
        address token1;
        bool useVaultDeposit;
        int256 startEdge;
        int256 stopEdge;
        uint256 amount0Desired;
        uint256 amount1Desired;
        uint256 amount0Min;
        uint256 amount1Min;
    }

    enum PaymentType {
        WALLET,
        COLLATERAL_SWAP
    }

    struct CallbackData {
        address token0;
        address token1;
        bool useVaultDeposit;
        address caller;
        address payer; // wallet that token is taken from when extraData is empty, or wallet record in Vault that credit from and refund when extraData is NewLoan
        PaymentType paymentType;
        bytes extraData; // currently having extraData simply means it is a newLoan call, refactor while there is more requirement
    }

    struct SwapInfo {
        address swapForwarder;
        address tokenInSpender;
        address to;
        bytes data;
    }

    struct BatchActionsParams {
        uint256[] unwindTokenIds;
        ReflowParams[] reflowParams;
        ResetParams[] resetParams;
        NewLoan.NewLoanParams[] newLoanParams;
        uint256[] noOpIds;
        Spot.SpotSwapParams infinityPoolSpotSwapParams;
        SwapInfo swap;
    }

    struct ReflowParams {
        uint256 tokenId;
        Quad tokenMix;
        bool fixedToken;
        int256 twapUntil;
    }

    struct ResetParams {
        uint256 tokenId;
        int256 deadEra;
        Quad tokenMix;
        bool fixedToken;
        int256 twapUntil;
    }

    error InvalidTokenOrder();
    error NoTokensProvided();
    error PoolDoesNotExist();
    error NoTokensRequired();
    error NoLiquidity();
    error PriceSlippageAmount0();
    error PriceSlippageAmount1();

    /*
     * @param tokenA address of tokenA
     * @param tokenB address of tokenB
     * @param splits the splits
     * @return (poolAddress, token0, token1)
     */

    function getPoolAddress(address tokenA, address tokenB, int256 splits) external view returns (address, address, address);

    function getPoolAddress(address tokenA, address tokenB) external view returns (address, address, address);

    /*
     * @return (factoryAddess)
     */
    function getFactoryAddress() external view returns (address);
}