// Created by Erez Volk.

import SwiftUI
import Combine

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 20) {
            HStack {
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
                .onKeyPress(keys: [.leftArrow]) { _ in
                    audioManager.prevDrone()
                    return .handled
                }
                .onKeyPress(keys: [.rightArrow]) { _ in
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

            // Volume Slider
            VStack {
                HStack {
                    Text("Volume")
                        .font(.headline)
                    Spacer()
                    Text("\(Int(audioManager.volume * 100))%")
                        .font(.subheadline)
                }
                .padding([.leading, .trailing], 40)

                Slider(value: $audioManager.volume, in: 0...1)
                    .padding([.leading, .trailing], 40)
            }
            .padding()
        }
        .padding()
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
