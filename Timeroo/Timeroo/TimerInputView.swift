//  Created by Erez Volk

import AppKit

class TimerInputView: NSView, NSTextFieldDelegate {
    let timeTextField = NSTextField()
    var onEnter: ((Int) -> Void)?
    var parentMenu: NSMenu?

    init(frame: NSRect, onEnter: ((Int) -> Void)?) {
        self.onEnter = onEnter
        super.init(frame: frame)

        timeTextField.placeholderString = "[hh:]mm:ss"
        timeTextField.frame = NSRect(x: 40, y: 0, width: 80, height: 24)
        timeTextField.alignment = .left
        timeTextField.delegate = self
        timeTextField.focusRingType = .default
        addSubview(timeTextField)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    func controlTextDidEndEditing(_ obj: Notification) {
        if let total = validateAndParse() {
            timeTextField.textColor = .labelColor
            onEnter?(total)
            parentMenu?.cancelTracking()
            timeTextField.stringValue = ""
        } else {
            timeTextField.textColor = .red
        }
    }

    func validateAndParse() -> Int? {
        let timeString = timeTextField.stringValue
        let parts = timeString.split(separator: ":")

        guard parts.count == 2 || parts.count == 3 else {
            return nil
        }

        guard let seconds = Int(parts[parts.count - 1]) else {
            return nil
        }
        guard seconds >= 0 && seconds < 60 else {
            return nil
        }

        guard let minutes = Int(parts[parts.count - 2]) else {
            return nil
        }
        guard minutes >= 0 && minutes < 60 else {
            return nil
        }

        if parts.count <= 2 {
            return seconds + 60 * minutes
        }

        guard let hours = Int(parts[0]) else {
            return nil
        }
        guard hours >= 0 else {
            return nil
        }

        return seconds + 60 * (minutes + 60 * hours)
    }
}
