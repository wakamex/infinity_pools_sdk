// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

library EncodeIdHelper {
    // This is used in encoding the ID of the NFT token. Make sure 0 represents LP and 1 represents Swapper
    enum PositionType {
        LP,
        Swapper
    }

    function encodeId(PositionType enumValue, address poolAddress, uint88 lpOrSwapperNumber) internal pure returns (uint256) {
        // Convert the enum value to uint256 and shift it to the left by 248 bits
        uint256 encodedEnum = uint256(uint8(enumValue)) << 248;
        // Convert the address to uint256 and shift it to the left by 88 bits
        uint256 encodedAddress = uint256(uint160(poolAddress)) << 88;
        // Combine the encoded enum, encoded address, and number using bitwise OR
        uint256 encodedId = encodedEnum | encodedAddress | lpOrSwapperNumber;
        return encodedId;
    }

    function decodeId(uint256 id) internal pure returns (PositionType, address, uint256) {
        // Extract the enum value by shifting the id to the right by 248 bits
        PositionType enumValue = PositionType(uint8(id >> 248));
        // Extract the address by shifting the id to the right by 88 bits and then masking the lower 160 bits
        address poolAddress = address(uint160(id >> 88));
        // Extract the number by applying a bitmask to the lower 88 bits of the id
        uint256 lpOrSwapperNumber = uint256(uint88(id));
        return (enumValue, poolAddress, lpOrSwapperNumber);
    }
}