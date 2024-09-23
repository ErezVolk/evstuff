// Created by Erez Volk.

import Foundation
import CloudKit

struct UserSettings: Codable {
    var customSequences: [String: [UInt8]] = [:]
    var selectedSequence: String = SequenceType.circleOfFourth.rawValue
}

class SettingsManager: ObservableObject {
    static let shared = SettingsManager()
    private let container = CKContainer.default()
    private let recordID = CKRecord.ID(recordName: "UserSettings")

    @Published var userSettings = UserSettings()

    private init() {
        loadSettings()
    }

    func saveSettings() {
        let encoder = JSONEncoder()
        if let data = try? encoder.encode(userSettings) {
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("UserSettings.data")
            try? data.write(to: url)

            let asset = CKAsset(fileURL: url)
            let record = CKRecord(recordType: "Settings", recordID: recordID)
            record["data"] = asset

            container.privateCloudDatabase.save(record) { _, error in
                if let error = error {
                    print("Error saving settings: \(error.localizedDescription)")
                } else {
                    print("Settings saved successfully.")
                }
            }
        }
    }

    func loadSettings() {
        container.privateCloudDatabase.fetch(withRecordID: recordID) { record, error in
            if let record = record, let asset = record["data"] as? CKAsset {
                if let data = try? Data(contentsOf: asset.fileURL!) {
                    let decoder = JSONDecoder()
                    if let settings = try? decoder.decode(UserSettings.self, from: data) {
                        DispatchQueue.main.async {
                            self.userSettings = settings
                        }
                    }
                }
            } else if let error = error {
                print("Error loading settings: \(error.localizedDescription)")
            }
        }
    }
}
