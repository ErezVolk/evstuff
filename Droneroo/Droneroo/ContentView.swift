// Created by Erez Volk.

import SwiftUI
import Combine

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @State private var selectedOrder: SequenceOrder = .forward
    @State private var delta = 0
    @State private var toggle = false
    @FocusState private var focused: Bool

    /// Convert a `SequenceOrder` constant to the SF shape we want for it
    private func orderShape(_ order: SequenceOrder) -> String {
        switch order {
        case .forward: return "arrow.forward"
        case .backward: return "arrow.backward"
        }
    }

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Spacer(minLength: 0).overlay {
                    HStack {
                        Spacer()

                        Button {
                            audioManager.prevDrone()
                        } label: {
                            Image(systemName: "backward.circle.fill").font(.title)
                        }
                    }
                }

                Button {
                    audioManager.toggleDrone()
                } label: {
                    Image(systemName: "playpause.circle.fill").font(.largeTitle)
                }.padding()

                Spacer(minLength: 0).overlay {
                    HStack {
                        Button {
                            audioManager.nextDrone()
                        } label: {
                            Image(systemName: "forward.circle.fill").font(.title)
                        }

                        Button {
                            audioManager.randomDrone()
                        } label: {
                            Image(systemName: "dice.fill")
                        }

                        Spacer()
                    }
                }
            }

            Text("Current note: \(audioManager.currentNoteName)")
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

            HStack {
                Picker("", selection: $selectedSequence) {
                    ForEach(SequenceType.allCases) { sequence in
                        Text(sequence.rawValue).tag(sequence)
                    }
                }
                .fixedSize()
                .onChange(of: selectedSequence) {
                    audioManager.sequenceType = selectedSequence
                    audioManager.loadSequence()
                }
                Picker("", selection: $selectedOrder) {
                    ForEach(SequenceOrder.allCases) { order in
                        Image(systemName: orderShape(order)).tag(order)
                    }
                }
                .pickerStyle(PalettePickerStyle())
                .fixedSize()
                .onChange(of: selectedOrder) { audioManager.sequenceOrder = selectedOrder }
            }

            // Instrument
            HStack {
#if os(macOS)
                Button("Load SoundFont") {
                    let panel = NSOpenPanel()
                    panel.allowsMultipleSelection = false
                    panel.canChooseDirectories = false
                    if panel.runModal() == .OK {
                        audioManager.loadInstrument(panel.url!)
                    }
                }
#endif
                Button("Default") {
                    audioManager.loadInstrument()
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
        }
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
