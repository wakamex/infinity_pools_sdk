// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface ISwapForwarder {
    function exactOutputSupported() external pure returns (bool);

    function swapExactInput(
        IERC20 tokenIn,
        address tokenInSpender,
        uint256 tokenAmountIn,
        IERC20 tokenOut,
        uint256 minTokenAmountOut,
        address to,
        bytes calldata data
    ) external returns (uint256 tokenOutAmount);

    function swapExactOutput(
        IERC20 tokenIn,
        address tokenInSpender,
        uint256 maxTokenAmountIn,
        IERC20 tokenOut,
        uint256 tokenAmountOut,
        address to,
        bytes calldata data
    ) external returns (uint256 tokenInAmount);
}