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

class AudioManager: NSObject, ObservableObject {
    @Published var currentNoteName: String = "None"
    @Published var volume: Float = 1.0
    @Published var instrument: String = "None"
    var sequenceType: SequenceType = .circleOfFourth
    private let velocity: UInt8 = 101
    private let sharps = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
    private let flats = ["C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"]
    private let audioEngine = AVAudioEngine()
    private var sampler = AVAudioUnitSampler()
    private var isPlaying = false
    private var noteSequence: [UInt8] = []
    private var nameSequence: [String] = []
    private var currentIndex = 0
    private var currentNote: UInt8!
    private var cancellables = Set<AnyCancellable>()
    // From http://johannes.roussel.free.fr/music/soundfonts.htm
    private let defaultInstrument = Bundle.main.url(forResource: "JR_String2", withExtension: "sf2")!
#if os(macOS)
    private var assertionID: IOPMAssertionID = 0
    private var sleepDisabled = false
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
                    program: 0, // TO DO: Make Configurable (echo 'inst 1' |fluidsynth foobar.sf2)
                    bankMSB: UInt8(kAUSampler_DefaultMelodicBankMSB),
                    bankLSB: UInt8(kAUSampler_DefaultBankLSB))
                instrument = actual.deletingPathExtension().lastPathComponent
                // not sure how to wait for it to be ready
                if wasPlaying { sleep(1) }
            } catch {
                print("Couldn't load instrument: \(error.localizedDescription)")
                newSampler()
            }
        }
    }

    func startDrone() {
        currentNote = noteSequence[currentIndex]
        currentNoteName = nameSequence[currentIndex]
        sampler.startNote(currentNote, withVelocity: velocity, onChannel: 0)
        sampler.startNote(currentNote + 12, withVelocity: velocity, onChannel: 0)
        isPlaying = true
        #if os(macOS)
        if !sleepDisabled {
            sleepDisabled = IOPMAssertionCreateWithName(
                kIOPMAssertionTypeNoDisplaySleep as CFString,
                IOPMAssertionLevel(kIOPMAssertionLevelOn),
                "Droneroo" as CFString,
                &assertionID) == kIOReturnSuccess
        }
        #else
        UIApplication.shared.isIdleTimerDisabled = true
        #endif
    }

    func stopDrone() {
        sampler.stopNote(currentNote, onChannel: 0)
        sampler.stopNote(currentNote + 12, onChannel: 0)
        isPlaying = false
        currentNoteName = "None"
        #if os(macOS)
        if sleepDisabled {
            IOPMAssertionRelease(assertionID)
            sleepDisabled = false
        }
        #else
        UIApplication.shared.isIdleTimerDisabled = false
        #endif
    }

    func toggleDrone() {
        if isPlaying {
            stopDrone()
        } else {
            startDrone()
        }
    }

    func prevDrone() {
        changeDrone(-1)
    }

    func nextDrone() {
        changeDrone(1)
    }

    func changeDrone(_ delta: Int) {
        timeOut { _ in
            currentIndex = (currentIndex + noteSequence.count + delta) % noteSequence.count
        }
    }

    private func timeOut(_ hey: (_ wasPlaying: Bool) -> Void) {
        let wasPlaying = isPlaying
        if wasPlaying { stopDrone() }
        hey(wasPlaying)
        if wasPlaying { startDrone() }
    }

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
        var idx = sharps.firstIndex(of: note)
        if idx == nil {
            idx = flats.firstIndex(of: note)
        }
        return UInt8(48 + idx!)
    }
}
