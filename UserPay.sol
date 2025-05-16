// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad, isPositive, isZero} from "src/types/ABDKMathQuad/Quad.sol";
import {ceil} from "src/types/ABDKMathQuad/Math.sol";
import {PoolState} from "src/interfaces/IInfinityPoolState.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {IInfinityPoolPaymentCallback} from "src/interfaces/IInfinityPoolPaymentCallback.sol";

library UserPay {
    // Convention of UserPay.Info from library calls are in human unit
    struct Info {
        Quad token0;
        Quad token1;
    }

    error UserPayToken0Mismatch(int256 expectedToken0, int256 expectedToken1);
    error UserPayToken1Mismatch(int256 expectedToken0, int256 expectedToken1);

    function translateQuantities(Info memory amounts, PoolState storage pool) internal view returns (int256, int256) {
        Quad amount0 = amounts.token0 * pool.tenToPowerDecimals0; // in wei
        Quad amount1 = amounts.token1 * pool.tenToPowerDecimals1; // in wei
        return (round(amount0), round(amount1));
    }

    /**
     *  amount > 0 => user pays
     *  amount < 0 => user receives
     */
    function makeUserPay(Info memory amounts, PoolState storage pool, address to, bytes calldata data)
        public
        returns (int256 expectedToken0, int256 expectedToken1)
    {
        (expectedToken0, expectedToken1) = translateQuantities(amounts, pool);

        if (expectedToken0 < 0) SafeERC20.safeTransfer(IERC20(pool.token0), to, uint256(-expectedToken0));
        if (expectedToken1 < 0) SafeERC20.safeTransfer(IERC20(pool.token1), to, uint256(-expectedToken1));

        if (data.length > 0) {
            uint256 balance0Before = IERC20(pool.token0).balanceOf(address(this));
            uint256 balance1Before = IERC20(pool.token1).balanceOf(address(this));
            IInfinityPoolPaymentCallback(msg.sender).infinityPoolPaymentCallback(expectedToken0, expectedToken1, data);

            if (expectedToken0 > 0 && IERC20(pool.token0).balanceOf(address(this)) < balance0Before + uint256(expectedToken0)) {
                revert UserPayToken0Mismatch(expectedToken0, expectedToken1);
            }

            if (expectedToken1 > 0 && IERC20(pool.token1).balanceOf(address(this)) < balance1Before + uint256(expectedToken1)) {
                revert UserPayToken1Mismatch(expectedToken0, expectedToken1);
            }
        } else {
            if (expectedToken0 > 0) SafeERC20.safeTransferFrom(IERC20(pool.token0), msg.sender, address(this), uint256(expectedToken0));
            if (expectedToken1 > 0) SafeERC20.safeTransferFrom(IERC20(pool.token1), msg.sender, address(this), uint256(expectedToken1));
        }
    }

    function makeUserPay(Info memory amounts, PoolState storage pool, bytes calldata data)
        internal
        returns (int256 expectedToken0, int256 expectedToken1)
    {
        return makeUserPay(amounts, pool, msg.sender, data);
    }

    // always round to +infinity so that user pay more and receive less
    function round(Quad amount) internal pure returns (int256) {
        return ceil(amount);
    }
}