//  Created by Erez Volk

import SwiftUI

@main
struct TimerooApp: App {
    @NSApplicationDelegateAdaptor(TimerooAppDelegate.self) var appDelegate

    var body: some Scene {
        Settings { EmptyView() }
    }
}
