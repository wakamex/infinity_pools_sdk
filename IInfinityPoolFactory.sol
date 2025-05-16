// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

interface IInfinityPoolFactory {
    event OwnerChanged(address indexed oldOwner, address indexed newOwner);
    event PoolCreated(address indexed token0, address indexed token1, int256 splits, address pool, uint8 decimals0, uint8 decimals1);

    function owner() external view returns (address);
    function getPool(address tokenA, address tokenB, int256 splits) external view returns (address pool);
    function getPool(address tokenA, address tokenB) external view returns (address pool);

    function createPool(address tokenA, address tokenB, int256 splits) external returns (address pool);
}