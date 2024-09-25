//  Created by Erez Volk

import AppKit

class PopoverWindow: NSPanel {
    override var canBecomeKey: Bool {
        return true
    }
    
    override var canBecomeMain: Bool {
        return false
    }
}
