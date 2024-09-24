import Cocoa
import UserNotifications

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var timer: Timer?
    var totalTime: TimeInterval = 0
    var isPaused: Bool = true
    let stopwatch = NSImage( // https://github.com/sam4096/apple-sf-symbols-list
        systemSymbolName: "stopwatch.fill",
        accessibilityDescription: "timer"
    )

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        // Remove the app from Force Quit menu
        NSApplication.shared.setActivationPolicy(.prohibited)
        
        // Create Status Bar Item
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        // Set initial title
        updateStatusBarTitle()
        
        // Create the menu
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Start/Pause", action: #selector(startPauseTimer), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Clear", action: #selector(clearTimer), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quitApplication), keyEquivalent: ""))
        statusItem.menu = menu

        // Request Notification Permissions
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert]) { granted, error in
            if granted {
                print("Permission granted for notifications")
            } else if let error = error {
                print("Failed to request notification permission: \(error)")
            }
        }
    }
    
    func applicationWillTerminate(_ aNotification: Notification) {
        // Stop the timer if active
        timer?.invalidate()
    }

    @objc func startPauseTimer() {
        if isPaused {
            // Start the timer
            timer = Timer.scheduledTimer(
                timeInterval: 1.0,
                target: self,
                selector: #selector(updateTimer),
                userInfo: nil,
                repeats: true
            )
            isPaused = false
            updateStatusBarTitle()
            
            if totalTime == 0 {
                sendNotification("Starting")
            } else {
                sendNotification("Resuming at \(getTimeString())")
            }
        } else {
            // Pause the timer
            timer?.invalidate()
            timer = nil
            isPaused = true
            updateStatusBarTitle()
            sendNotification("Pausing at \(getTimeString())")
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
            statusItem.button?.image = stopwatch
            statusItem.button?.title = ""
            statusItem.button?.appearsDisabled = false
        } else {
            statusItem.button?.image = nil
            statusItem.button?.title = getTimeString()
            statusItem.button?.appearsDisabled = isPaused
        }
    }

    func getTimeString() -> String {
        let now = totalTime
        let minutes = Int(now) / 60
        let seconds = Int(now) % 60
        let title = String(format: "%02d:%02d", minutes, seconds)
        return title
    }
    
    func sendNotification(_ body: String) {
        let content = UNMutableNotificationContent()
        content.title = "Timeroo"
        content.body = body
        
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Failed to deliver notification: \(error)")
            }
        }
    }
}
