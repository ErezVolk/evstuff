// Created by Erez Volk.

import Foundation
import AVFoundation
import SwiftUI
import Combine
#if os(macOS)
import IOKit.pwr_mgt
#endif

enum SequenceType: String, CaseIterable, Identifiable {
    case circleOfFourth = "Circle of Fourths"
    case rayBrown = "Ray Brown"
    case chromatic = "Chromatic"
    var id: String { self.rawValue }
}

/// Ordering of sequence; the values are system image names
enum SequenceOrder: CaseIterable, Identifiable {
    case forward
    case backward
    var id: Self { self }
}

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

class AudioManager: NSObject, ObservableObject {
    @Published var currentNoteName: String = "None"
    @Published var previousNoteName: String = "N/A"
    @Published var nextNoteName: String = "N/A"
    @Published var volume: Float = 1.0
    @Published var instrument: String = "None"
    @Published var isPlaying = false
    var sequenceType: SequenceType = .circleOfFourth
    var sequenceOrder: SequenceOrder = .forward
    private let whoAmI = getWhoAmI()
    private let velocity: UInt8 = 101
    private let sharps = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
    private let flats = ["C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"]
    private let audioEngine = AVAudioEngine()
    private var sampler = AVAudioUnitSampler()
    private var noteSequence: [UInt8] = []
    private var nameSequence: [String] = []
    private var currentIndex = 0
    private var currentNote: UInt8!
    private var cancellables = Set<AnyCancellable>()
    // From http://johannes.roussel.free.fr/music/soundfonts.htm
    private let defaultInstrument = Bundle.main.url(forResource: "JR_String2", withExtension: "sf2")!
#if os(macOS)
    private var assertionID: IOPMAssertionID = 0
#endif

    override init() {
        super.init()
        setupAudioEngine()
    }

    private func setupAudioEngine() {
        connectSampler()

        // Set initial volume
        audioEngine.mainMixerNode.outputVolume = volume

        // Observe volume changes
        $volume
            .receive(on: RunLoop.main)
            .sink { [weak self] newVolume in
                self?.audioEngine.mainMixerNode.outputVolume = newVolume
            }
            .store(in: &cancellables)

        do {
            try audioEngine.start()
        } catch {
            print("Audio Engine couldn't start: \(error.localizedDescription)")
        }
    }

    /// Reset to the default Beep sound
    func resetInstrument() {
        timeOut { _ in
            newSampler()
        }
    }

    /// Recreate sample, resetting to beep (internal fucntion, called when not playing)
    private func newSampler() {
        audioEngine.detach(sampler)
        sampler = AVAudioUnitSampler()
        instrument = "None"
    }

    private func connectSampler() {
        audioEngine.attach(sampler)
        audioEngine.connect(sampler, to: audioEngine.mainMixerNode, format: nil)
    }

    /// Load a SoundFont file
    func loadInstrument(_ url: URL? = nil) {
        timeOut { wasPlaying in
            do {
                let actual = url ?? defaultInstrument
                try sampler.loadSoundBankInstrument(
                    at: actual,
                    program: 0,
                    bankMSB: UInt8(kAUSampler_DefaultMelodicBankMSB),
                    bankLSB: UInt8(kAUSampler_DefaultBankLSB))
                instrument = actual.deletingPathExtension().lastPathComponent

                if wasPlaying {
                    // Loading a new instrument can disable sound, so flip off and on after a short delay
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.timeOut { _ in /* NOP */ } }
                }
            } catch {
                print("Couldn't load instrument: \(error.localizedDescription)")
                newSampler()
            }
        }
    }

    /// Start playing.
    func startDrone() {
        currentNote = noteSequence[currentIndex]
        currentNoteName = nameSequence[currentIndex]
        previousNoteName = nameSequence[(currentIndex + nameSequence.count - 1) % nameSequence.count]
        nextNoteName = nameSequence[(currentIndex + 1) % nameSequence.count]
        sampler.startNote(currentNote, withVelocity: velocity, onChannel: 0)
        sampler.startNote(currentNote + 12, withVelocity: velocity, onChannel: 0)
        setIsPlaying(true)
    }

    /// Stop playing.
    func stopDrone() {
        guard isPlaying else { return }
        sampler.stopNote(currentNote, onChannel: 0)
        sampler.stopNote(currentNote + 12, onChannel: 0)
        setIsPlaying(false)
    }
    
    /// Set the `isPlaying` flag, and also try to disable screen sleeping
    func setIsPlaying(_ newValue: Bool) {
        if newValue == isPlaying { return }
        isPlaying = newValue
        
        #if os(macOS)
        if newValue {
            let status = IOPMAssertionCreateWithName(
                kIOPMAssertionTypeNoDisplaySleep as CFString,
                IOPMAssertionLevel(kIOPMAssertionLevelOn),
                whoAmI as CFString,
                &assertionID)
            if status != kIOReturnSuccess {
                print("Cannot disable sleep: \(status)")
                assertionID = 0
            }
        } else {
            IOPMAssertionRelease(assertionID)
            assertionID = 0
        }
        #else
        UIApplication.shared.isIdleTimerDisabled = newValue
        #endif
    }

    /// Pause/Play.
    func toggleDrone() {
        if isPlaying {
            stopDrone()
        } else {
            startDrone()
        }
    }

    /// Move to the next note in the current sequence
    func prevDrone() {
        changeDrone(-1)
    }

    /// Move to the next note in the current sequence
    func nextDrone() {
        changeDrone(1)
    }
    
    /// Switch to a random note in the current sequence
    func randomDrone() {
        changeDrone(Int.random(in: 1...noteSequence.count))
    }

    /// Update the current note, based on `delta` and `sequenceOrder`
    func changeDrone(_ delta: Int) {
        let n = noteSequence.count
        let uncut: Int
        switch sequenceOrder {
        case .forward: uncut = currentIndex + delta
        case .backward: uncut = currentIndex - delta
        }
        timeOut { _ in
            currentIndex = ((uncut % n) + n) % n
        }
    }

    private func timeOut(_ hey: (_ wasPlaying: Bool) -> Void) {
        let wasPlaying = isPlaying
        if wasPlaying { stopDrone() }
        hey(wasPlaying)
        if wasPlaying { startDrone() }
    }

    /// Configure the actual sequence of notes, based on `sequenceType`.
    func loadSequence() {
        timeOut { _ in
            currentIndex = 0
            switch sequenceType {
            case .circleOfFourth:
                nameSequence = ["C", "F", "A♯/B♭", "D♯/E♭", "G♯/A♭", "C♯/D♭", "F♯/G♭", "B", "E", "A", "D", "G"]
            case .rayBrown:
                nameSequence = ["C", "F", "B♭", "E♭", "A♭", "D♭", "G", "D", "A", "E", "B", "F♯"]
            case .chromatic:
                nameSequence = ["C", "C♯/D♭", "D", "D♯/E♭", "E", "F", "F♯/G♭", "G", "G♯/A♭", "A", "A♯/B♭", "B"]
            }
            noteSequence = nameSequence.map { noteNameToMidiNumber($0) }
        }
    }

    private func noteNameToMidiNumber(_ noteName: String) -> UInt8 {
        let note = String(noteName.prefix(2))
        let idx = sharps.firstIndex(of: note) ?? flats.firstIndex(of: note)
        return UInt8(48 + idx!)
    }
}
