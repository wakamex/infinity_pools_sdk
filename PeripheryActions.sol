// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.20;

import {IInfinityPoolFactory} from "src/interfaces/IInfinityPoolFactory.sol";
import {IInfinityPool} from "src/interfaces/IInfinityPool.sol";
import {lowEdgeTub} from "src/libraries/helpers/PoolHelper.sol";
import {Quad, fromUint256, fromInt256, POSITIVE_ONE, POSITIVE_ZERO} from "src/types/ABDKMathQuad/Quad.sol";
import {min} from "src/types/ABDKMathQuad/Math.sol";
import {EncodeIdHelper} from "src/periphery/libraries/EncodeIdHelper.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {IInfinityPoolsPeriphery} from "src/periphery/interfaces/IInfinityPoolsPeriphery.sol";
import {Spot} from "src/libraries/external/Spot.sol";
import {NewLoan} from "src/libraries/external/NewLoan.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ISwapForwarder} from "src/periphery/interfaces/ISwapForwarder.sol";
import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import {VaultActions} from "src/periphery/libraries/external/VaultActions.sol";

library PeripheryActions {
    using SafeCast for int256;

    event PeripheryLiquidityAdded(address indexed user, address indexed pool, uint256 indexed lpNum, int256 amount0, int256 amount1, int256 earnEra);

    event SpotSwap(
        address fromToken, uint256 fromTokenAmount, uint256 fromTokenReceived, address toToken, uint256 toTokenAmount, uint256 toTokenReceived
    );
    event NoOpSwapperIds(uint256[] ids);

    // Custom Errors
    error IdenticalTokens();
    error NoTokensProvided();
    error PoolDoesNotExist();
    error NoTokensRequired();
    error NoLiquidity();
    error PriceSlippageAmount0();
    error PriceSlippageAmount1();
    error InvalidTokenOrder();
    error InvalidPoolAddress();
    error InvalidSwapForwarder();
    error InvalidTokenAddress();
    error OwnerIsNotTheSame();
    error PoolAddressIsNotTheSame();
    error PositionTypeIsNotSwapper();
    error CallerNotApproved();
    error InvalidID();
    error InvalidFundsSpent();
    error NotEnoughCollateral(int256 net0, int256 net1);

    function addLiquidity(address factory, IInfinityPoolsPeriphery.AddLiquidityParams memory params) external returns (uint256 tokenIdToMint) {
        if (params.token0 == params.token1) revert IdenticalTokens();
        if (params.token0 >= params.token1) revert InvalidTokenOrder();
        if (params.amount0Desired == 0 && params.amount1Desired == 0) revert NoTokensProvided();

        address poolAddress = IInfinityPoolFactory(factory).getPool(params.token0, params.token1);
        if (poolAddress == address(0)) revert PoolDoesNotExist();

        IInfinityPool infPool = IInfinityPool(poolAddress);

        int256 startTub = lowEdgeTub(params.startEdge);
        int256 stopTub = lowEdgeTub(params.stopEdge);

        Quad liquidity;
        {
            (int256 amount0PerLiq, int256 amount1PerLiq) = infPool.getPourQuantities(startTub, stopTub, POSITIVE_ONE);
            if (amount0PerLiq <= 0 && amount1PerLiq <= 0) revert NoTokensRequired();

            if (amount0PerLiq == 0) {
                liquidity = fromUint256(params.amount1Desired) / fromInt256(amount1PerLiq);
            } else if (amount1PerLiq == 0) {
                liquidity = fromUint256(params.amount0Desired) / fromInt256(amount0PerLiq);
            } else {
                Quad liq0 = fromUint256(params.amount0Desired) / fromInt256(amount0PerLiq);
                Quad liq1 = fromUint256(params.amount1Desired) / fromInt256(amount1PerLiq);
                liquidity = min(liq0, liq1);
            }
        }
        if (liquidity <= POSITIVE_ZERO) revert NoLiquidity();

        uint256 lpNum;
        int256 amount0;
        int256 amount1;
        int256 earnEra;

        {
            IInfinityPoolsPeriphery.CallbackData memory callbackData = IInfinityPoolsPeriphery.CallbackData({
                token0: params.token0,
                token1: params.token1,
                useVaultDeposit: params.useVaultDeposit,
                caller: msg.sender,
                payer: msg.sender, // msg.sender of this function = user = payer,
                paymentType: IInfinityPoolsPeriphery.PaymentType.WALLET,
                extraData: ""
            });

            (lpNum, amount0, amount1, earnEra) = infPool.pour(startTub, stopTub, liquidity, abi.encode(callbackData));
        }

        tokenIdToMint = EncodeIdHelper.encodeId(EncodeIdHelper.PositionType.LP, poolAddress, uint88(lpNum));
        if (amount0.toUint256() < params.amount0Min) revert PriceSlippageAmount0();
        if (amount1.toUint256() < params.amount1Min) revert PriceSlippageAmount1();

        emit PeripheryLiquidityAdded(msg.sender, poolAddress, lpNum, amount0, amount1, earnEra);
    }

    function newLoan(
        address factory,
        address token0,
        address token1,
        int256 splits,
        address onBehalfOf,
        NewLoan.NewLoanParams calldata params,
        Spot.SpotSwapParams calldata infinityPoolSpotSwapParams,
        IInfinityPoolsPeriphery.SwapInfo calldata swap
    ) external returns (uint256 tokenIdToMint) {
        if (token0 >= token1) revert InvalidTokenOrder();
        address poolAddress = IInfinityPoolFactory(factory).getPool(token0, token1, splits);
        if (poolAddress == address(0)) revert InvalidPoolAddress();
        IInfinityPool infPool = IInfinityPool(poolAddress);
        IInfinityPoolsPeriphery.CallbackData memory callbackData = IInfinityPoolsPeriphery.CallbackData({
            token0: token0,
            token1: token1,
            useVaultDeposit: false,
            caller: msg.sender,
            payer: onBehalfOf,
            paymentType: IInfinityPoolsPeriphery.PaymentType.COLLATERAL_SWAP,
            extraData: abi.encode(swap)
        });

        if (infinityPoolSpotSwapParams.remainingAmount.isDefined()) {
            IInfinityPool.Action[] memory actions = new IInfinityPool.Action[](2);
            bytes[] memory actionDatas = new bytes[](2);
            // newloan and then swap
            actions[0] = IInfinityPool.Action.NEW_LOAN;
            actionDatas[0] = abi.encode(params);

            actions[1] = IInfinityPool.Action.SWAP;
            actionDatas[1] = abi.encode(infinityPoolSpotSwapParams);

            infPool.doActions(actions, actionDatas, address(this), abi.encode(callbackData));
        } else {
            infPool.newLoan(params, abi.encode(callbackData));
        }

        uint256 swappersCount = infPool.getSwappersCount();
        tokenIdToMint = EncodeIdHelper.encodeId(EncodeIdHelper.PositionType.Swapper, poolAddress, uint88(swappersCount - 1));
    }

    function handleSwap(
        mapping(address => bool) storage swapForwarders,
        IERC20 fromToken,
        uint256 fromTokenAmount,
        IERC20 toToken,
        uint256 toTokenAmount,
        bool shouldExactOutput,
        IInfinityPoolsPeriphery.SwapInfo memory swapInfo
    ) public returns (uint256 fromTokenReceived, uint256 toTokenReceived) {
        if (swapInfo.swapForwarder == address(0)) revert InvalidSwapForwarder();
        if (!swapForwarders[swapInfo.swapForwarder]) revert InvalidSwapForwarder();

        SafeERC20.safeTransfer(fromToken, swapInfo.swapForwarder, fromTokenAmount);

        uint256 fromTokenBalanceBefore = fromToken.balanceOf(address(this));
        uint256 toTokenBalanceBefore = toToken.balanceOf(address(this));

        if (shouldExactOutput && ISwapForwarder(swapInfo.swapForwarder).exactOutputSupported()) {
            ISwapForwarder(swapInfo.swapForwarder).swapExactOutput(
                fromToken, swapInfo.tokenInSpender, fromTokenAmount, toToken, toTokenAmount, swapInfo.to, swapInfo.data
            );
        } else {
            ISwapForwarder(swapInfo.swapForwarder).swapExactInput(
                fromToken, swapInfo.tokenInSpender, fromTokenAmount, toToken, toTokenAmount, swapInfo.to, swapInfo.data
            );
        }
        fromTokenReceived = fromToken.balanceOf(address(this)) - fromTokenBalanceBefore;
        toTokenReceived = toToken.balanceOf(address(this)) - toTokenBalanceBefore;
        emit SpotSwap(address(fromToken), fromTokenAmount, fromTokenReceived, address(toToken), toTokenAmount, toTokenReceived);
    }

    function getPoolAddress(address factory, address tokenA, address tokenB) external view returns (address, address, address) {
        if (tokenA == tokenB) revert IdenticalTokens();
        (address token0, address token1) = tokenA < tokenB ? (tokenA, tokenB) : (tokenB, tokenA);
        if (token0 == address(0)) revert InvalidTokenAddress();
        address poolAddress = IInfinityPoolFactory(factory).getPool(token0, token1);
        if (poolAddress == address(0)) revert InvalidPoolAddress();
        return (poolAddress, token0, token1);
    }

    function isApprovedForAll(address owner, address operator) public view returns (bool) {
        return IERC721(address(this)).isApprovedForAll(owner, operator);
    }

    // we call the public functions of periphery contracts externally
    function isAuthorized(address owner, address spender, uint256 tokenId) public view returns (bool) {
        return
            spender != address(0) && (owner == spender || isApprovedForAll(owner, spender) || IERC721(address(this)).getApproved(tokenId) == spender);
    }

    function ownerOf(uint256 tokenId) public view returns (address) {
        return IERC721(address(this)).ownerOf(tokenId); // this external ownerOf method in ERC721 makes sure the owner of tokenId is not zero address
    }

    function processAction(uint256 tokenId, address poolAddress, address owner) public view returns (uint256) {
        (EncodeIdHelper.PositionType positionType, address _poolAddress, uint256 swapperNum) = EncodeIdHelper.decodeId(tokenId);
        if (poolAddress != _poolAddress) revert PoolAddressIsNotTheSame();
        if (ownerOf(tokenId) != owner) revert OwnerIsNotTheSame();
        if (!isAuthorized(ownerOf(tokenId), msg.sender, tokenId)) revert CallerNotApproved();
        if (positionType != EncodeIdHelper.PositionType.Swapper) revert PositionTypeIsNotSwapper();

        return swapperNum;
    }

    function handleSwapper(uint256 tokenId, IInfinityPoolsPeriphery.SwapInfo memory swap)
        public
        view
        returns (address poolAddress, uint256 swapperNum, bytes memory callbackData)
    {
        EncodeIdHelper.PositionType positionType;
        (positionType, poolAddress, swapperNum) = EncodeIdHelper.decodeId(tokenId);
        if (positionType != EncodeIdHelper.PositionType.Swapper) revert InvalidID();
        if (!isAuthorized(ownerOf(tokenId), msg.sender, tokenId)) revert CallerNotApproved();

        (address token0, address token1,) = IInfinityPool(poolAddress).getPoolInfo();
        IInfinityPoolsPeriphery.CallbackData memory _callbackData = IInfinityPoolsPeriphery.CallbackData({
            token0: token0,
            token1: token1,
            useVaultDeposit: false,
            caller: msg.sender,
            payer: ownerOf(tokenId),
            paymentType: IInfinityPoolsPeriphery.PaymentType.COLLATERAL_SWAP,
            extraData: abi.encode(swap)
        });
        callbackData = abi.encode(_callbackData);
    }

    struct BatchActionLocalVars {
        uint256 length;
        IInfinityPool.Action[] actions;
        bytes[] actionDatas;
        address owner;
    }

    function batchActionsOnSwappers(IInfinityPoolsPeriphery.BatchActionsParams memory params) external returns (address, address, uint256) {
        BatchActionLocalVars memory vars;
        vars.length = params.unwindTokenIds.length + params.reflowParams.length + params.resetParams.length + params.newLoanParams.length
            + (params.infinityPoolSpotSwapParams.remainingAmount.isDefined() ? 1 : 0);
        if (params.noOpIds.length > 0) emit NoOpSwapperIds(params.noOpIds);
        if (vars.length == 0) return (address(0), address(0), 0);
        vars.actions = new IInfinityPool.Action[](vars.length);
        uint256 tokenId = params.unwindTokenIds.length != 0
            ? params.unwindTokenIds[0]
            : (params.reflowParams.length != 0 ? params.reflowParams[0].tokenId : params.resetParams[0].tokenId);
        vars.owner = ownerOf(tokenId);

        (address poolAddress,, bytes memory _callbackData) = handleSwapper(tokenId, params.swap);

        IInfinityPoolsPeriphery.CallbackData memory callbackData = abi.decode(_callbackData, (IInfinityPoolsPeriphery.CallbackData));
        uint256 actionDatasIdx;
        vars.actionDatas = new bytes[](vars.length);
        for (uint256 i; i < params.unwindTokenIds.length; i++) {
            uint256 unwindTokenId = params.unwindTokenIds[actionDatasIdx];
            vars.actions[actionDatasIdx] = IInfinityPool.Action.UNWIND;
            uint256 swapperNum = processAction(unwindTokenId, poolAddress, vars.owner);
            vars.actionDatas[actionDatasIdx] = abi.encode(swapperNum);
            actionDatasIdx++;
        }

        for (uint256 i; i < params.reflowParams.length; i++) {
            vars.actions[actionDatasIdx] = IInfinityPool.Action.REFLOW;
            IInfinityPoolsPeriphery.ReflowParams memory reflowParam = params.reflowParams[i];
            uint256 reflowTokenId = reflowParam.tokenId;
            uint256 swapperNum = processAction(reflowTokenId, poolAddress, vars.owner);
            vars.actionDatas[actionDatasIdx] = abi.encode(swapperNum, reflowParam.tokenMix, reflowParam.fixedToken, reflowParam.twapUntil);
            actionDatasIdx++;
        }

        for (uint256 i; i < params.resetParams.length; i++) {
            vars.actions[actionDatasIdx] = IInfinityPool.Action.RESET;
            IInfinityPoolsPeriphery.ResetParams memory resetParam = params.resetParams[i];
            uint256 resetTokenId = resetParam.tokenId;
            uint256 swapperNum = processAction(resetTokenId, poolAddress, vars.owner);
            vars.actionDatas[actionDatasIdx] = abi.encode(swapperNum, resetParam.deadEra, resetParam.tokenMix, resetParam.fixedToken, resetParam.twapUntil);
            actionDatasIdx++;
        }

        for (uint256 i; i < params.newLoanParams.length; i++) {
            vars.actions[actionDatasIdx] = IInfinityPool.Action.NEW_LOAN;
            vars.actionDatas[actionDatasIdx] = abi.encode(params.newLoanParams[i]);
            actionDatasIdx++;
        }

        if (params.infinityPoolSpotSwapParams.remainingAmount.isDefined()) {
            vars.actions[actionDatasIdx] = IInfinityPool.Action.SWAP;
            vars.actionDatas[actionDatasIdx] = abi.encode(params.infinityPoolSpotSwapParams);
            actionDatasIdx++;
        }

        for (uint256 i; i < params.noOpIds.length; i++) {
            uint256 noOpId = params.noOpIds[i];
            processAction(noOpId, poolAddress, vars.owner);
        }

        if (vars.actions.length > 0) IInfinityPool(poolAddress).doActions(vars.actions, vars.actionDatas, address(this), abi.encode(callbackData));

        uint256 swappersCount = IInfinityPool(poolAddress).getSwappersCount();

        return (vars.owner, poolAddress, swappersCount);

        //this logic needs to stay in the periphery contract itself because we don't have access to _mint internal method in the library
        // for (uint256 i; i < params.newLoanParams.length; i++) {
        //     _mint(vars.owner, EncodeIdHelper.encodeId(EncodeIdHelper.PositionType.Swapper, poolAddress, uint88(swappersCount - 1 - i)));
        // }
    }

    function handleCollateralSwap(
        mapping(address user => mapping(address token0 => mapping(address token1 => mapping(bool isToken0 => uint256)))) storage collaterals,
        mapping(address swapForwarderAddress => bool) storage swapForwarders,
        address factory,
        bytes memory _data,
        int256 amount0,
        int256 amount1
    ) external {
        IInfinityPoolsPeriphery.CallbackData memory data = abi.decode(_data, (IInfinityPoolsPeriphery.CallbackData));

        int256 collateral0 = int256(collaterals[data.payer][data.token0][data.token1][false]);
        int256 collateral1 = int256(collaterals[data.payer][data.token0][data.token1][true]);

        int256 net0 = collateral0 - amount0;
        int256 net1 = collateral1 - amount1;

        if (net0 < 0) {
            // token1 to token0
            if (net1 <= 0) revert NotEnoughCollateral(net0, net1);
            IInfinityPoolsPeriphery.SwapInfo memory swap = abi.decode(data.extraData, (IInfinityPoolsPeriphery.SwapInfo));
            (uint256 token1Received, uint256 token0Received) =
                handleSwap(swapForwarders, IERC20(data.token1), uint256(net1), IERC20(data.token0), uint256(-net0), true, swap);
            net0 += int256(token0Received);
            net1 = int256(token1Received); //direct assignment since all net1 to taken to handleSwap so it is 0 + token1Received
        } else if (net1 < 0) {
            // token0 to token1
            if (net0 <= 0) revert NotEnoughCollateral(net0, net1);
            IInfinityPoolsPeriphery.SwapInfo memory swap = abi.decode(data.extraData, (IInfinityPoolsPeriphery.SwapInfo));
            (uint256 token0Received, uint256 token1Received) =
                handleSwap(swapForwarders, IERC20(data.token0), uint256(net0), IERC20(data.token1), uint256(-net1), true, swap);
            net0 = int256(token0Received); //direct assignment since all net0 to taken to handleSwap so it is 0 + token0Received
            net1 += int256(token1Received);
        }

        if (net0 < 0 || net1 < 0) revert InvalidFundsSpent();

        int256 collateralUsed0 = collateral0 - net0;
        int256 collateralUsed1 = collateral1 - net1;

        if (collateralUsed0 > 0) {
            if (data.caller != data.payer) if (!isApprovedForAll(data.payer, data.caller)) revert CallerNotApproved();
            VaultActions._decreaseCollateral(
                collaterals, factory, data.token0, data.token1, IERC20(data.token0), data.payer, address(this), uint256(collateralUsed0)
            );
        } else if (collateralUsed0 < 0) {
            VaultActions._increaseCollateral(
                collaterals, factory, data.token0, data.token1, IERC20(data.token0), data.payer, address(this), uint256(-collateralUsed0)
            );
        }

        if (collateralUsed1 > 0) {
            if (data.caller != data.payer) if (!isApprovedForAll(data.payer, data.caller)) revert CallerNotApproved();
            VaultActions._decreaseCollateral(
                collaterals, factory, data.token0, data.token1, IERC20(data.token1), data.payer, address(this), uint256(collateralUsed1)
            );
        } else if (collateralUsed1 < 0) {
            VaultActions._increaseCollateral(
                collaterals, factory, data.token0, data.token1, IERC20(data.token1), data.payer, address(this), uint256(-collateralUsed1)
            );
        }
    }
}