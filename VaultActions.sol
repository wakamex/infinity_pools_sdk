// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.20;

import {Address} from "@openzeppelin/contracts/utils/Address.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IPermit2} from "src/periphery/interfaces/external/IPermit2.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IInfinityPoolFactory} from "src/interfaces/IInfinityPoolFactory.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {Z, I} from "src/Constants.sol";

library VaultActions {
    using Address for address;
    using Address for address payable;
    using SafeERC20 for IERC20;

    event Deposit(address indexed token, address indexed to, uint256 amount);
    event Withdraw(address indexed token, address indexed from, uint256 amount);
    event DepositCollateral(address indexed user, address indexed poolAddress, bool token, uint8 decimals, address source, uint256 amount);
    event WithdrawCollateral(address indexed user, address indexed poolAddress, bool token, uint8 decimals, address destination, uint256 amount);

    error NonExistentToken();
    error VaultERC20InsufficientAllowance(address token, address owner, address spender, uint256 allowance, uint256 needed);
    error NotEnoughDeposit();
    error InvalidToken();
    error ETHTransferFailed();

    function depositERC20(
        mapping(address => mapping(address => uint256)) storage deposits,
        IPermit2 permit2,
        IERC20 token,
        address to,
        uint256 amount,
        bool isPermit2,
        uint256 nonce,
        uint256 deadline,
        bytes calldata signature
    ) external {
        if (isPermit2) {
            if (address(token).code.length == 0) revert NonExistentToken();
            permit2.permitTransferFrom(
                IPermit2.PermitTransferFrom({permitted: IPermit2.TokenPermissions({token: token, amount: amount}), nonce: nonce, deadline: deadline}),
                IPermit2.SignatureTransferDetails({to: address(this), requestedAmount: amount}),
                msg.sender,
                signature
            );
        } else {
            SafeERC20.safeTransferFrom(token, msg.sender, address(this), amount);
        }
        _depositERC20(deposits, address(token), to, amount);
    }

    function _depositERC20(mapping(address => mapping(address => uint256)) storage deposits, address token, address to, uint256 amount) public {
        deposits[to][token] += amount;
        emit Deposit(token, to, amount);
    }

    function addCollateralCapped(
        mapping(address => mapping(address => uint256)) storage deposits,
        mapping(address user => mapping(address token0 => mapping(address token1 => mapping(bool isToken0 => uint256)))) storage collaterals,
        mapping(address user => mapping(address token => mapping(address spender => uint256))) storage allowance,
        address factory,
        address tokenA,
        address tokenB,
        IERC20 token,
        address user,
        uint256 amount
    ) external returns (uint256) {
        amount = _withdrawERC20Capped(deposits, allowance, token, user, address(this), amount);
        (address token0, address token1) = tokenA < tokenB ? (tokenA, tokenB) : (tokenB, tokenA);
        _increaseCollateral(collaterals, factory, token0, token1, token, user, user, amount);
        return amount;
    }

    function _increaseCollateral(
        mapping(address user => mapping(address token0 => mapping(address token1 => mapping(bool isToken0 => uint256)))) storage collaterals,
        address factory,
        address token0,
        address token1,
        IERC20 token,
        address user,
        address source,
        uint256 amount
    ) public {
        bool boolToken = _getToken(token0, token1, address(token));

        collaterals[user][token0][token1][boolToken] += amount;
        address poolAddress = IInfinityPoolFactory(factory).getPool(token0, token1);
        uint8 decimals = IERC20Metadata(address(token)).decimals();
        emit DepositCollateral(user, poolAddress, boolToken, decimals, source, amount);
    }

    function _getToken(address token0, address token1, address token) public pure returns (bool) {
        if (token == token1) return I;
        if (token == token0) return Z;
        revert InvalidToken();
    }

    function _decreaseCollateral(
        mapping(address user => mapping(address token0 => mapping(address token1 => mapping(bool isToken0 => uint256)))) storage collaterals,
        address factory,
        address token0,
        address token1,
        IERC20 token,
        address user,
        address destination,
        uint256 amount
    ) public {
        bool boolToken = _getToken(token0, token1, address(token));

        collaterals[user][token0][token1][boolToken] -= amount;
        address poolAddress = IInfinityPoolFactory(factory).getPool(token0, token1);
        uint8 decimals = IERC20Metadata(address(token)).decimals();
        emit WithdrawCollateral(user, poolAddress, boolToken, decimals, destination, amount);
    }

    function _withdrawERC20Capped(
        mapping(address => mapping(address => uint256)) storage deposits,
        mapping(address user => mapping(address token => mapping(address spender => uint256))) storage allowance,
        IERC20 token,
        address onBehalfOf,
        address to,
        uint256 amount
    ) public returns (uint256) {
        if (amount == type(uint256).max) amount = deposits[onBehalfOf][address(token)];
        if (msg.sender != onBehalfOf) _spendAllowance(allowance, address(token), onBehalfOf, msg.sender, amount);

        _withdrawERC20WithoutCheckingForAllowance(deposits, token, onBehalfOf, to, amount);
        
        return amount;
    }

    function _withdrawERC20WithoutCheckingForAllowance(
        mapping(address => mapping(address => uint256)) storage deposits,
        IERC20 token,
        address onBehalfOf,
        address to,
        uint256 amount
    ) public {
        if (deposits[onBehalfOf][address(token)] < amount) revert NotEnoughDeposit();
        deposits[onBehalfOf][address(token)] -= amount;
        if (to != address(this)) SafeERC20.safeTransfer(token, to, amount);
        emit Withdraw(address(token), onBehalfOf, amount);
    }

    function _spendAllowance(
        mapping(address user => mapping(address token => mapping(address spender => uint256))) storage allowance,
        address token,
        address owner,
        address spender,
        uint256 value
    ) public {
        uint256 currentAllowance = allowance[owner][token][spender];
        if (currentAllowance < value) revert VaultERC20InsufficientAllowance(token, owner, spender, currentAllowance, value);
        allowance[owner][token][spender] = currentAllowance - value;
    }

    function approveERC20(
        mapping(address user => mapping(address token => mapping(address spender => uint256))) storage allowance,
        IERC20 token,
        address spender,
        uint256 amount
    ) external {
        allowance[msg.sender][address(token)][spender] = amount;
    }

    function increaseAllowanceERC20(
        mapping(address user => mapping(address token => mapping(address spender => uint256))) storage allowance,
        IERC20 token,
        address spender,
        uint256 amount
    ) external {
        allowance[msg.sender][address(token)][spender] += amount;
    }
}