// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.20;

import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IUniswapV2Router02} from "src/periphery/interfaces/external/IUniswapV2Router02.sol";
import {ISwapForwarder} from "src/periphery/interfaces/ISwapForwarder.sol";

contract GeneralSwapForwarder is ISwapForwarder {
    uint256 MAX_INT_DEADLINE = 2 ** 256 - 1;

    using SafeERC20 for IERC20;

    error SwapFailed();
    error InsufficientOutputAmount();
    error ExcessiveInputAmount();

    function exactOutputSupported() external pure override returns (bool) {
        return true;
    }

    function swapExactInput(
        IERC20 tokenIn,
        address tokenInSpender,
        uint256 tokenAmountIn,
        IERC20 tokenOut,
        uint256 minTokenAmountOut,
        address to,
        bytes calldata data
    ) external returns (uint256 tokenOutAmount) {
        tokenIn.forceApprove(tokenInSpender, tokenAmountIn);
        if (data.length > 0) {
            (bool success,) = to.call(data);
            if (!success) revert SwapFailed();
        }
        tokenOutAmount = tokenOut.balanceOf(address(this));
        if (tokenOutAmount < minTokenAmountOut) revert InsufficientOutputAmount();
        tokenOut.safeTransfer(msg.sender, tokenOutAmount);
        if (tokenIn.balanceOf(address(this)) > 0) tokenIn.safeTransfer(msg.sender, tokenIn.balanceOf(address(this)));
        tokenIn.forceApprove(tokenInSpender, 0);
    }

    function swapExactOutput(
        IERC20 tokenIn,
        address tokenInSpender,
        uint256 maxTokenAmountIn,
        IERC20 tokenOut,
        uint256 tokenAmountOut,
        address to,
        bytes calldata data
    ) external returns (uint256 tokenInAmount) {
        tokenIn.forceApprove(tokenInSpender, maxTokenAmountIn);
        uint256 tokenInBalanceBefore = tokenIn.balanceOf(address(this));
        if (data.length > 0) {
            (bool success,) = to.call(data);
            if (!success) revert SwapFailed();
        }
        tokenInAmount = tokenInBalanceBefore - tokenIn.balanceOf(address(this));
        if (tokenInAmount > maxTokenAmountIn) revert ExcessiveInputAmount();
        tokenOut.safeTransfer(msg.sender, tokenAmountOut);
        if (tokenInAmount < maxTokenAmountIn) tokenIn.safeTransfer(msg.sender, maxTokenAmountIn - tokenInAmount);
        tokenIn.forceApprove(tokenInSpender, 0);
    }
}