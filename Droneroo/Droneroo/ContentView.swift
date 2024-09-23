// Created by Erez Volk.

import SwiftUI
import Combine

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @State private var delta = 0
    @State private var toggle = false
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Button {
                    audioManager.prevDrone()
                } label: {
                    Text("⏮")
                        .font(.title)
                        .cornerRadius(10)
                }

                Button {
                    audioManager.toggleDrone()
                } label: {
                    Text("⏯")
                        .font(.title)
                        .cornerRadius(10)
                }

                Button {
                    audioManager.nextDrone()
                } label: {
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
                .onAppear {
                    focused = true
                }
                .onKeyPress(keys: [.leftArrow]) { _ in
                    delta -= 1
                    return .handled
                }
                .onKeyPress(keys: [.rightArrow]) { _ in
                    delta += 1
                    return .handled
                }
                .onChange(of: delta) {
                    if delta != 0 { audioManager.changeDrone(delta) }
                    delta = 0
                }
                .onKeyPress(keys: [.space]) { _ in
                    toggle = !toggle
                    return .handled
                }
                .onChange(of: toggle) {
                    if toggle {audioManager.toggleDrone()}
                    toggle = false
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

            // Instrument
            HStack {
                Button("Load SoundFont") {
                    let panel = NSOpenPanel()
                    panel.allowsMultipleSelection = false
                    panel.canChooseDirectories = false
                    if panel.runModal() == .OK {
                        audioManager.loadInstrument(panel.url!)
                    }
                }
                Button("Reset") {
                    audioManager.resetInstrument()
                }
                Text(audioManager.instrument)
                    .monospaced()
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
