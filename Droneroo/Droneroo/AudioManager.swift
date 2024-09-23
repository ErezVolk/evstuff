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
    var sequenceType: SequenceType = .circleOfFourth
    private let velocity: UInt8 = 101
    private let sharps = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
    private let flats = ["C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"]
    private var audioEngine = AVAudioEngine()
    private var sampler = AVAudioUnitSampler()
    private var isPlaying = false
    private var noteSequence: [UInt8] = []
    private var nameSequence: [String] = []
    private var currentIndex = 0
    private var currentNote: UInt8 = 60 // Default to Middle C
    private var cancellables = Set<AnyCancellable>()
    // From http://johannes.roussel.free.fr/music/soundfonts.htm
    private let organ = Bundle.main.url(forResource: "organ", withExtension: "sf2")!
#if os(macOS)
    private var assertionID: IOPMAssertionID = 0
    private var sleepDisabled = false
#endif
    
    override init() {
        super.init()
        setupAudioEngine()
    }
    
    private func setupAudioEngine() {
        loadInstrument(organ)
        audioEngine.attach(sampler)
        audioEngine.connect(sampler, to: audioEngine.mainMixerNode, format: nil)
        
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
    
    func loadInstrument(_ at: URL) {
        timeOut { () in
            do {
                try sampler.loadSoundBankInstrument(at: at, program: 0, bankMSB: 0x79, bankLSB: 0)
                // not sure how to wait for it to be ready
                sleep(1)
            } catch {
                print("Couldn't load instrument: \(error.localizedDescription)")
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
                "Drone Playing" as CFString,
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
        timeOut { () in
            currentIndex = (currentIndex + noteSequence.count + delta) % noteSequence.count
        }
    }

    private func timeOut(_ hey: () -> ()) {
        let wasPlaying = isPlaying
        if wasPlaying { stopDrone() }
        hey()
        if wasPlaying { startDrone() }
    }
    
    func loadSequence() {
        timeOut { () in
            currentIndex = 0
            switch sequenceType {
            case .circleOfFourth:
                nameSequence = ["C", "F", "A♯/B♭", "D♯/E♭", "G♯/A♭", "C♯/D♭", "F♯/G♭", "B", "E", "A", "D", "G"]
            case .rayBrown:
                nameSequence = ["C", "F", "B♭", "E♭", "A♭", "D♭", "G", "D", "A", "E", "B", "F♯"]
            case .chromatic:
                nameSequence = sharps
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
