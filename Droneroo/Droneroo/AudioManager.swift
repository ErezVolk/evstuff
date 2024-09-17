//
//  AUdioManager.swift
//  Droneroo
//
//  Created by Erez Volk on 17/09/2024.
//

import Foundation
import AVFoundation
import SwiftUI

enum SequenceType: String, CaseIterable, Identifiable {
    case circleOfFourth = "Circle of Fourths"
    case rayBrown = "Ray Brown"
    case chromatic = "Chromatic"
    var id: String { self.rawValue }
}

class AudioManager: NSObject, ObservableObject {
    private let sharps = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
    private let flats = ["C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"]
    private var audioEngine = AVAudioEngine()
    private var sampler = AVAudioUnitSampler()
    @Published var isPlaying = false
    var sequenceType: SequenceType = .circleOfFourth
    private var noteSequence: [UInt8] = []
    private var nameSequence: [String] = []
    private var currentIndex = 0
    private var currentNote: UInt8 = 60 // Default to Middle C
    @Published var currentNoteName: String = "None"

    override init() {
        super.init()
        setupAudioEngine()
    }

    private func setupAudioEngine() {
        audioEngine.attach(sampler)
        audioEngine.connect(sampler, to: audioEngine.mainMixerNode, format: nil)

        do {
            try audioEngine.start()
        } catch {
            print("Audio Engine couldn't start: \(error.localizedDescription)")
        }
    }

    func startDrone() {
        currentNote = noteSequence[currentIndex]
        currentNoteName = nameSequence[currentIndex]
        sampler.startNote(currentNote, withVelocity: 64, onChannel: 0)
        isPlaying = true
    }

    func stopDrone() {
        sampler.stopNote(currentNote, onChannel: 0)
        isPlaying = false
        currentNoteName = "None"
    }

    func toggleDrone() {
        if isPlaying {
            stopDrone()
        } else {
            startDrone()
        }
    }

    func nextDrone() {
        if isPlaying {
            stopDrone()
        }
        currentIndex = (currentIndex + 1) % noteSequence.count
        startDrone()
    }

    func loadSequence() {
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
        if isPlaying {
            stopDrone()
            startDrone()
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

