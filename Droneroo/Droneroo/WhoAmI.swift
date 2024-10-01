//  Created by Erez Volk on 01/10/2024.

import CoreFoundation
import Foundation

/// Helper to get a value from the bundle's info dictionary
fileprivate func getBundleProperty(_ key: CFString) -> String {
    return Bundle.main.infoDictionary?[key as String] as? String ?? "???"
}

/// Just for fun, figure out our name and version programmatically
func getWhoAmI() -> String {
    let app = getBundleProperty(kCFBundleNameKey)
    let ver = getBundleProperty(kCFBundleVersionKey)
    return "\(app) v\(ver)"
}
