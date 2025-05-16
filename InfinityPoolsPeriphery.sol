// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.20;

import {IInfinityPoolFactory} from "src/interfaces/IInfinityPoolFactory.sol";
import {TUBS} from "src/Constants.sol";
import {IInfinityPoolsPeriphery} from "src/periphery/interfaces/IInfinityPoolsPeriphery.sol";
import {IInfinityPool} from "src/interfaces/IInfinityPool.sol";
import {Quad, fromUint256, fromInt256, POSITIVE_ONE, POSITIVE_ZERO} from "src/types/ABDKMathQuad/Quad.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {min} from "src/types/ABDKMathQuad/Math.sol";
import {lowEdgeTub} from "src/libraries/helpers/PoolHelper.sol";
import {Structs} from "src/libraries/external/Structs.sol";
import {IInfinityPoolPaymentCallback} from "src/interfaces/IInfinityPoolPaymentCallback.sol";
import {CallbackValidation} from "./libraries/CallbackValidation.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ERC721Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC721/ERC721Upgradeable.sol";
import {NewLoan} from "src/libraries/external/NewLoan.sol";
import {IPermit2} from "src/periphery/interfaces/external/IPermit2.sol";
import {GeneralSwapForwarder} from "src/periphery/swapForwarders/GeneralSwapForwarder.sol";
import {Context} from "@openzeppelin/contracts/utils/Context.sol";
import {EncodeIdHelper} from "./libraries/EncodeIdHelper.sol";
import {OptInt256} from "src/types/Optional/OptInt256.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {PeripheryActions} from "src/periphery/libraries/external/PeripheryActions.sol";
import {IInfinityPoolFactory} from "src/interfaces/IInfinityPoolFactory.sol";
import {ISwapForwarder} from "src/periphery/interfaces/ISwapForwarder.sol";
import {Z, I} from "src/Constants.sol";
import {Spot} from "src/libraries/external/Spot.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";
import {PeripheryPayment} from "src/periphery/PeripheryPayment.sol";

contract InfinityPoolsPeriphery is UUPSUpgradeable, ERC721Upgradeable, PeripheryPayment, IInfinityPoolsPeriphery, IInfinityPoolPaymentCallback {
    using SafeCast for int256;

    error InvalidFundsSpent();
    error Unauthorized();
    error IdenticalTokens();
    error InvalidPoolAddress();
    error NotEnoughCollateral(int256 net0, int256 net1);
    error InvalidID();
    error CallerNotApproved();
    error InvalidPaymentType();
    error PoolAddressIsNotTheSame();
    error OwnerIsNotTheSame();
    error PositionTypeIsNotSwapper();

    /**
     * EVENTS *
     */
    event PeripheryLiquidityAdded(address indexed user, address indexed pool, uint256 indexed lpNum, int256 amount0, int256 amount1, int256 earnEra);

    event NoOpSwapperIds(uint256[] ids);

    /**
     * @custom:oz-upgrades-unsafe-allow state-variable-immutable
     */
    GeneralSwapForwarder public immutable generalSwapForwarder = new GeneralSwapForwarder();

    function _authorizeUpgrade(address) internal view override {
        if (msg.sender != IInfinityPoolFactory(factory).owner()) revert Unauthorized();
    }

    function initialize(address _factory, address _WETH9, IPermit2 permit2) public initializer {
        factory = _factory;
        WETH9 = _WETH9;
        __Vault_init(permit2);
        __ERC721_init("InfinityPools: Positions NFT", "INF-POS");

        swapForwarders[address(generalSwapForwarder)] = true;
    }

    function addOrRemoveSwapForwarder(address swapForwarder, bool addOrRemove) external nonReentrant {
        if (msg.sender != IInfinityPoolFactory(factory).owner()) revert Unauthorized();
        swapForwarders[swapForwarder] = addOrRemove;
    }

    /*
     * @return (factoryAddress)
     */
    function getFactoryAddress() public view override returns (address) {
        return factory;
    }

    /*
     * @param tokenA address of tokenA
     * @param tokenB address of tokenB
     * @param splits the splits
     * @return (poolAddress, token0, token1)
     */
    function getPoolAddress(address tokenA, address tokenB, int256) public view override returns (address, address, address) {
        return getPoolAddress(tokenA, tokenB);
    }

    function getPoolAddress(address tokenA, address tokenB) public view returns (address, address, address) {
        return PeripheryActions.getPoolAddress(factory, tokenA, tokenB);
    }

    /**
     *  requires token0 < token1
     */
    function addLiquidity(IInfinityPoolsPeriphery.AddLiquidityParams memory params) external payable nonReentrant {
        /// @custom:oz-upgrades-unsafe-allow external-library-linking
        uint256 tokenIdToMint = PeripheryActions.addLiquidity(factory, params);
        _mint(msg.sender, tokenIdToMint);
    }

    function infinityPoolPaymentCallback(int256 amount0, int256 amount1, bytes calldata _data) external {
        CallbackData memory data = abi.decode(_data, (CallbackData));
        //msg.sender = pool contract
        CallbackValidation.verifyCallback(factory, data.token0, data.token1);

        if (data.paymentType == PaymentType.COLLATERAL_SWAP) {
            PeripheryActions.handleCollateralSwap(collaterals, swapForwarders, factory, _data, amount0, amount1);

            // msg.sender = pool, send funds to pool to fit user pay
            if (amount0 > 0) SafeERC20.safeTransfer(IERC20(data.token0), msg.sender, uint256(amount0));
            if (amount1 > 0) SafeERC20.safeTransfer(IERC20(data.token1), msg.sender, uint256(amount1));
        } else if (data.paymentType == PaymentType.WALLET) {
            //negative amount has already been paid to the receiver
            if (amount0 > 0) pay(IERC20(data.token0), data.payer, msg.sender, data.useVaultDeposit, uint256(amount0));
            if (amount1 > 0) pay(IERC20(data.token1), data.payer, msg.sender, data.useVaultDeposit, uint256(amount1));
        } else {
            revert InvalidPaymentType();
        }
    }

    function newLoan(
        address token0,
        address token1,
        int256 splits,
        address onBehalfOf,
        NewLoan.NewLoanParams calldata newLoanParams,
        Spot.SpotSwapParams calldata infinityPoolSpotSwapParams,
        SwapInfo calldata swap
    ) public nonReentrant {
        if (msg.sender != onBehalfOf) if (!isApprovedForAll(onBehalfOf, msg.sender)) revert CallerNotApproved();

        uint256 tokenIdToMint = PeripheryActions.newLoan(factory, token0, token1, splits, onBehalfOf, newLoanParams, infinityPoolSpotSwapParams, swap);
        _mint(onBehalfOf, tokenIdToMint);
    }

    function batchActionsOnSwappers(
        uint256[] calldata unwindTokenIds,
        ReflowParams[] calldata reflowParams,
        NewLoan.NewLoanParams[] calldata newLoanParams,
        uint256[] calldata noOpIds,
        Spot.SpotSwapParams calldata infinityPoolSpotSwapParams,
        SwapInfo calldata swap
    ) public {
        BatchActionsParams memory params = BatchActionsParams({
            unwindTokenIds: unwindTokenIds,
            reflowParams: reflowParams,
            resetParams: new ResetParams[](0),
            newLoanParams: newLoanParams,
            noOpIds: noOpIds,
            infinityPoolSpotSwapParams: infinityPoolSpotSwapParams,
            swap: swap
        });
        batchActionsOnSwappers(params);
    }

    function batchActionsOnSwappers(BatchActionsParams memory params) public nonReentrant {
        (address owner, address poolAddress, uint256 swappersCount) = PeripheryActions.batchActionsOnSwappers(params);

        for (uint256 i; i < params.newLoanParams.length; i++) {
            _mint(owner, EncodeIdHelper.encodeId(EncodeIdHelper.PositionType.Swapper, poolAddress, uint88(swappersCount - 1 - i)));
        }
    }

    function unwind(uint256 tokenId, SwapInfo calldata swap) public nonReentrant returns (int256 amount0, int256 amount1) {
        (address poolAddress, uint256 swapperNum, bytes memory _callbackData) = PeripheryActions.handleSwapper(tokenId, swap);
        return IInfinityPool(poolAddress).unwind(swapperNum, address(this), _callbackData);
    }

    function reset(ResetParams memory params, SwapInfo calldata swap) public nonReentrant returns (int256 amount0, int256 amount1) {
        (address poolAddress, uint256 swapperNum, bytes memory _callbackData) = PeripheryActions.handleSwapper(params.tokenId, swap);

        return IInfinityPool(poolAddress).reset(
            swapperNum,
            OptInt256.wrap(params.deadEra),
            params.tokenMix,
            params.fixedToken,
            OptInt256.wrap(params.twapUntil),
            address(this),
            _callbackData
        );
    }

    function reflow(ReflowParams memory params, SwapInfo calldata swap) public nonReentrant returns (int256 amount0, int256 amount1) {
        (address poolAddress, uint256 swapperNum, bytes memory _callbackData) = PeripheryActions.handleSwapper(params.tokenId, swap);

        return IInfinityPool(poolAddress).reflow(
            swapperNum, params.tokenMix, params.fixedToken, OptInt256.wrap(params.twapUntil), address(this), _callbackData
        );
    }

    function drain(uint256 tokenId, address receiver) public nonReentrant returns (int256 amount0, int256 amount1) {
        (EncodeIdHelper.PositionType positionType, address poolAddress, uint256 lpNum) = EncodeIdHelper.decodeId(tokenId);
        if (positionType != EncodeIdHelper.PositionType.LP) revert InvalidID();
        if (!_isAuthorized(_requireOwned(tokenId), msg.sender, tokenId)) revert CallerNotApproved();

        return IInfinityPool(poolAddress).drain(lpNum, receiver, "");
    }

    function collect(uint256 tokenId, address receiver) public nonReentrant returns (int256 amount0, int256 amount1) {
        (EncodeIdHelper.PositionType positionType, address poolAddress, uint256 lpNum) = EncodeIdHelper.decodeId(tokenId);
        if (positionType != EncodeIdHelper.PositionType.LP) revert InvalidID();
        if (!_isAuthorized(_requireOwned(tokenId), msg.sender, tokenId)) revert CallerNotApproved();

        return IInfinityPool(poolAddress).collect(lpNum, receiver, "");
    }

    function tap(uint256 tokenId) public nonReentrant {
        (EncodeIdHelper.PositionType positionType, address poolAddress, uint256 lpNum) = EncodeIdHelper.decodeId(tokenId);
        if (positionType != EncodeIdHelper.PositionType.LP) revert InvalidID();

        return IInfinityPool(poolAddress).tap(lpNum);
    }

    function encodeId(EncodeIdHelper.PositionType enumValue, address poolAddress, uint88 lpOrSwapperNumber) public pure returns (uint256) {
        return EncodeIdHelper.encodeId(enumValue, poolAddress, lpOrSwapperNumber);
    }

    function swapDeposit(address user, IERC20 fromToken, uint256 fromTokenAmount, IERC20 toToken, uint256 minTokenAmountOut, SwapInfo memory swapInfo)
        external
        nonReentrant
    {
        fromTokenAmount = _withdrawERC20Capped(fromToken, user, address(this), fromTokenAmount); //if user!=msg.sender, it will check for approval
        (uint256 fromTokenReceived, uint256 toTokenReceived) =
            PeripheryActions.handleSwap(swapForwarders, fromToken, fromTokenAmount, toToken, minTokenAmountOut, false, swapInfo);

        if (fromTokenReceived > 0) _depositERC20(address(fromToken), user, fromTokenReceived); //most of the time fromTokenReceived is 0
        if (toTokenReceived > 0) _depositERC20(address(toToken), user, toTokenReceived);
    }

    function withdrawCollaterals(address token0, address token1, address user, bool token, uint256 amount) external nonReentrant {
        if (token0 == token1) revert IdenticalTokens();
        if (token0 >= token1) revert InvalidTokenOrder();

        if (user != msg.sender) if (!isApprovedForAll(user, msg.sender)) revert CallerNotApproved();
        uint256 collateralBalance = collaterals[user][token0][token1][token];
        if (amount == type(uint256).max) amount = collateralBalance;

        if (token == Z) {
            if (amount > collateralBalance) revert NotEnoughCollateral(-int256(amount), 0);
            _decreaseCollateral(token0, token1, IERC20(token0), user, user, amount);
            _depositERC20(token0, user, amount);
        } else {
            if (amount > collateralBalance) revert NotEnoughCollateral(0, -int256(amount));
            _decreaseCollateral(token0, token1, IERC20(token1), user, user, amount);
            _depositERC20(token1, user, amount);
        }
    }

    // the NFT image will be fetched from below baseURI
    function _baseURI() internal view override returns (string memory) {
        return string.concat("https://nft.infinitypools.finance/", Strings.toString(block.chainid), "/");
    }
}