(*

To install a global hotkey for Timeroo, the best and easiest way I know is with
BetterTouchTool. I've tried Shortcuts and Automoator and found them too
cumbersome and slow for this task.

*)

(* tell application "Timeroo" to activate *)

tell application "System Events"
    tell Process "Timeroo"
        click menu item "Start/Pause" of menu 1 of menu bar item 1 of menu bar 2
    end tell
end tell
