// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

interface IInfinityPoolPaymentCallback {
    function infinityPoolPaymentCallback(int256 amount0, int256 amount1, bytes calldata data) external;
}