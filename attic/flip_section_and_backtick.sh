#!/bin/sh

echo "This lasts only until restart. Follow the instructions in com.erezvolk.flipkeys.plist to run on login."

/usr/bin/hidutil property \
    --matching '[{"Product":"Apple Internal Keyboard / Trackpad"},{"Product":"Magic Keyboard"},{"Product":"Magic Keyboard with Numeric Keypad"},{"Product":"Magic Keyboard with Touch ID"},{"Product":"Magic Keyboard with Touch ID and Numeric Keypad"}]' \
    --set '{"UserKeyMapping":[{"HIDKeyboardModifierMappingSrc":0x700000035,"HIDKeyboardModifierMappingDst":0x700000064},{"HIDKeyboardModifierMappingSrc":0x700000064,"HIDKeyboardModifierMappingDst":0x700000035}]}'
