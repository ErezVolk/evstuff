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
    case chromatic = "Chromatic"
    var id: String { self.rawValue }
}

class AudioManager: NSObject, ObservableObject {
    private var audioEngine = AVAudioEngine()
    private var sampler = AVAudioUnitSampler()
    @Published var isPlaying = false
    var sequenceType: SequenceType = .circleOfFourth
    private var noteSequence: [UInt8] = []
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
        sampler.startNote(currentNote, withVelocity: 64, onChannel: 0)
        isPlaying = true
        currentNoteName = midiNoteNumberToName(currentNote)
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
            noteSequence = generateCircleOfFourthSequence()
        case .chromatic:
            noteSequence = Array(48...72) // C2 to C4
        }
    }

    private func generateCircleOfFourthSequence() -> [UInt8] {
        let circleOfFourths = [0, 5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7] // In semitones
        return circleOfFourths.map { UInt8(60 + $0) } // Starting from Middle C (60)
    }

    // Bluetooth Pedal Integration
    @objc func nextDroneCommand() {
        nextDrone()
    }

    @objc func toggleDroneCommand() {
        toggleDrone()
    }
    
    private func midiNoteNumberToName(_ noteNumber: UInt8) -> String {
        let noteNames = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
        let noteIndex = Int(noteNumber) % 12
        let octave = (Int(noteNumber) / 12) - 1
        let noteName = noteNames[noteIndex]
        return "\(noteName)\(octave)"
    }
}

