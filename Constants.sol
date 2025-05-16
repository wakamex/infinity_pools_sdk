// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Quad} from "./types/ABDKMathQuad/Quad.sol";
import {OPT_INT256_NONE, OptInt256, wrap} from "./types/Optional/OptInt256.sol";
import {OptQuad, toOptQuad} from "./types/Optional/OptQuad.sol";

int8 constant JUMPS = 13;
int8 constant JUMP_NONE = type(int8).max;
uint256 constant MIN_SPLITS = 12;
uint256 constant MAX_SPLITS = 19;
uint256 constant TICK_SUB_SLITS = MAX_SPLITS - MIN_SPLITS + 1;

int256 constant TUBS = int256(1 << MIN_SPLITS);

int256 constant DEADERA_NONE = OPT_INT256_NONE;

uint128 constant LOG_WORD_SIZE = 7;

int128 constant WORD_SIZE = int128(int128(1) << LOG_WORD_SIZE);

bool constant Z = false;
bool constant I = true;

int256 constant EPOCH = 1735740000;

OptInt256 constant NEVER_AGO = OptInt256.wrap(-1 << 30);
//precalulated values
// Step 0: 0.9996616064962437
// Step 1: 0.9993233275026507
// Step 2: 0.9986471128909702
// Step 3: 0.9972960560854701
// Step 4: 0.9945994234836332
// Step 5: 0.9892280131939755
// Step 6: 0.9785720620877001
// Step 7: 0.9576032806985737
// Step 8: 0.9170040432046712
// Step 9: 0.8408964152537145
// Step 10: 0.7071067811865476
// Step 11: 0.5
// Step 12: 0.25

Quad constant DEFLATOR_STEP_0 = Quad.wrap(bytes16(0x3ffeffd3a565efb64eabbbe3a5146f15));
Quad constant DEFLATOR_STEP_1 = Quad.wrap(bytes16(0x3ffeffa74ea381efc217a773f15c025f));
Quad constant DEFLATOR_STEP_2 = Quad.wrap(bytes16(0x3ffeff4eaca4391b5da33e743691f72a));
Quad constant DEFLATOR_STEP_3 = Quad.wrap(bytes16(0x3ffefe9d96b2a23d914a6037442fde32));
Quad constant DEFLATOR_STEP_4 = Quad.wrap(bytes16(0x3ffefd3c22b8f71f10975ba4b32bcf3a));
Quad constant DEFLATOR_STEP_5 = Quad.wrap(bytes16(0x3ffefa7c1819e90d82e90a7e74b263c2));
Quad constant DEFLATOR_STEP_6 = Quad.wrap(bytes16(0x3ffef50765b6e4540674f84b762862bb));
Quad constant DEFLATOR_STEP_7 = Quad.wrap(bytes16(0x3ffeea4afa2a490d9858f73a18f5db30));
Quad constant DEFLATOR_STEP_8 = Quad.wrap(bytes16(0x3ffed5818dcfba48725da05aeb66e0dd));
Quad constant DEFLATOR_STEP_9 = Quad.wrap(bytes16(0x3ffeae89f995ad3ad5e8734d1773205a));
Quad constant DEFLATOR_STEP_10 = Quad.wrap(bytes16(0x3ffe6a09e667f3bcc908b2fb1366ea95));
Quad constant DEFLATOR_STEP_11 = Quad.wrap(bytes16(0x3ffe0000000000000000000000000000));
Quad constant DEFLATOR_STEP_12 = Quad.wrap(bytes16(0x3ffd0000000000000000000000000000));

//np.log(np.float128(2))
Quad constant LAMBDA = Quad.wrap(bytes16(0x3ffe62e42fefa39ef35793c7673007e5));

Quad constant LOG1PPC = Quad.wrap(0x3ff8460d6ccca3676b71e159f1d244a4);

// 	final val minRate = 1e-3 / 365.2425 / ln2 // 0.1% annually
Quad constant MIN_RATE = Quad.wrap(0x3fed0913e12d7aa29793a679b84dd45f);
Quad constant UTILISATION_CAP = Quad.wrap(0x3ffefae147ae147ae147ae147ae147ae); // 0.99

Quad constant LN2 = Quad.wrap(bytes16(0x3ffe62e42fefa39ef35793c7673007e6));

Quad constant TWAP_SPREAD_DEFAULT = Quad.wrap(bytes16(0x3ff1a36e2eb1c432ca57a786c226809d));

// PERIODIC_APPROX = [
//     (0.4706553526183245, -0.05091131334578034, -0.0732538714640282, -0.007292900708078191),
//     (0.5925716471806282, -0.060926965128963895, -0.09017229010013399, -0.009913238478984947)]

Quad constant PERIODIC_APPROX_CONSTANT_0 = Quad.wrap(bytes16(0x3ffde1f37a0cbb71e000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_1 = Quad.wrap(bytes16(0xbffaa110c33a210dd000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_2 = Quad.wrap(bytes16(0xbffb2c0c4063e4eba000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_3 = Quad.wrap(bytes16(0xbff7ddf29208bf6f8000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_4 = Quad.wrap(bytes16(0x3ffe2f658d0a5af4c000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_5 = Quad.wrap(bytes16(0xbffaf31d1b558cc20000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_6 = Quad.wrap(bytes16(0xbffb71587fcfc49bb000000000000000));
Quad constant PERIODIC_APPROX_CONSTANT_7 = Quad.wrap(bytes16(0xbff844d6458847bbc000000000000000));

Quad constant NAN = Quad.wrap(bytes16(0x7fff0000000000000000000000000001));
OptQuad constant OPT_QUAD_NONE = OptQuad.wrap(Quad.unwrap(NAN));