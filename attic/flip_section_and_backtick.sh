#!/bin/sh

echo "This lasts only until restart. Follow the instructions in com.erezvolk.flipkeys.plist to run on login."

apple_keyboards=$(
    /usr/bin/hidutil list \
        | awk '$4 == 1 && $5 == 6 && ($1 == "0x4c" || $1 == "0x5ac") { print $1, $2 }' \
        | sort -u \
        | awk '{ printf ",{\"VendorID\":%s,\"ProductID\":%s}", $1, $2 }'
)

/usr/bin/hidutil property \
    --matching "[{\"Product\":\"Apple Internal Keyboard / Trackpad\"}$apple_keyboards]" \
    --set '{"UserKeyMapping":[{"HIDKeyboardModifierMappingSrc":0x700000035,"HIDKeyboardModifierMappingDst":0x700000064},{"HIDKeyboardModifierMappingSrc":0x700000064,"HIDKeyboardModifierMappingDst":0x700000035}]}'
