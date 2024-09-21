import Cocoa

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var timer: Timer?
    var totalTime: TimeInterval = 0
    var isPaused: Bool = true

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        // Remove the app from Force Quit menu
        NSApplication.shared.setActivationPolicy(.prohibited)
        
        // Create Status Bar Item
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        // Set initial title
        updateStatusBarTitle()
        
        // Create the menu
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Start/Pause", action: #selector(startPauseTimer), keyEquivalent: "s"))
        menu.addItem(NSMenuItem(title: "Clear", action: #selector(clearTimer), keyEquivalent: "c"))
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quitApplication), keyEquivalent: "q"))
        statusItem.menu = menu
        
        // Add scriptability
        NSAppleEventManager.shared().setEventHandler(self, andSelector: #selector(handleAppleScript(_:withReplyEvent:)), forEventClass: UInt32(kAECoreSuite), andEventID: UInt32(kAEDoScript))
    }
    
    func applicationWillTerminate(_ aNotification: Notification) {
        // Stop the timer if active
        timer?.invalidate()
    }

    @objc func startPauseTimer() {
        if isPaused {
            // Start the timer
            timer = Timer.scheduledTimer(timeInterval: 1.0, target: self, selector: #selector(updateTimer), userInfo: nil, repeats: true)
            isPaused = false
            updateStatusBarTitle()
        } else {
            // Pause the timer
            timer?.invalidate()
            timer = nil
            isPaused = true
            updateStatusBarTitle()
        }
    }
    
    @objc func updateTimer() {
        totalTime += 1
        updateStatusBarTitle()
    }
    
    @objc func clearTimer() {
        timer?.invalidate()
        timer = nil
        totalTime = 0
        isPaused = true
        updateStatusBarTitle()
    }
    
    @objc func quitApplication() {
        NSApplication.shared.terminate(self)
    }
    
    func updateStatusBarTitle() {
        if totalTime == 0 && isPaused {
            // Display Unicode clock symbol when the timer is zero and paused
            statusItem.button?.title = "🕒"
        } else {
            // Display the timer in MM:SS format
            let minutes = Int(totalTime) / 60
            let seconds = Int(totalTime) % 60
            let title = String(format: "%02d:%02d", minutes, seconds)
            
            if isPaused {
                // Greyed-out timer when paused
                statusItem.button?.attributedTitle = NSAttributedString(string: title, attributes: [.foregroundColor: NSColor.gray])
            } else {
                // Normal timer display when running
                statusItem.button?.title = title
            }
        }
    }
    
    // Handle AppleScript Start/Pause
    @objc dynamic func handleAppleScript(_ event: NSAppleEventDescriptor, withReplyEvent replyEvent: NSAppleEventDescriptor) {
        startPauseTimer()
    }
}
