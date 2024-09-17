//
//  ContentView.swift
//  Droneroo
//
//  Created by Erez Volk on 17/09/2024.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth

    var body: some View {
        VStack(spacing: 20) {
            Button(action: {
                audioManager.toggleDrone()
            }) {
                Text(audioManager.isPlaying ? "Pause Drone" : "Start Drone")
                    .font(.title)
                    .padding()
                    .background(Color.blue.opacity(0.7))
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }

            Button(action: {
                audioManager.nextDrone()
            }) {
                Text("Next Drone")
                    .font(.title)
                    .padding()
                    .background(Color.green.opacity(0.7))
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
            
            Text("Current Note: \(audioManager.currentNoteName)")
                .font(.headline)
                .padding()

            Picker("Sequence", selection: $selectedSequence) {
                ForEach(SequenceType.allCases) { sequence in
                    Text(sequence.rawValue).tag(sequence)
                }
            }
            .pickerStyle(SegmentedPickerStyle())
            .padding()
            .onChange(of: selectedSequence) {
                audioManager.sequenceType = selectedSequence
                audioManager.loadSequence()
            }
        }
        .padding()
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
