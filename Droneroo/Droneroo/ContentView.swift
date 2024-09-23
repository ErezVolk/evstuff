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
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 20) {
            HStack() {
                Button(action: {
                    audioManager.prevDrone()
                }) {
                    Text("⏮")
                        .font(.title)
                        .cornerRadius(10)
                }
                
                Button(action: {
                    audioManager.toggleDrone()
                }) {
                    Text("⏯")
                        .font(.title)
                        .cornerRadius(10)
                }
                
                Button(action: {
                    audioManager.nextDrone()
                }) {
                    Text("⏭")
                        .font(.title)
                        .cornerRadius(10)
                }
            }

            Text("Current Note: \(audioManager.currentNoteName)")
                .font(.headline)
                .padding()
                .focusable()
                .focused($focused)
                .onKeyPress(keys: [.leftArrow]) { press in
                    audioManager.prevDrone()
                    return .handled
                }
                .onKeyPress(keys: [.rightArrow]) { press in
                    audioManager.nextDrone()
                    return .handled
                }
                .onAppear {
                    focused = true
                }

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
