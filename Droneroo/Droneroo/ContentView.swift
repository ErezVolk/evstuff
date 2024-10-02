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
                Text(audioManager.previousNoteName)
                    .encircle(
                        diameter: 80,
                        textColor: audioManager.sequenceOrder == .backward ? .circleText : .otherCircleText,
                        circleColor: audioManager.sequenceOrder == .backward ? .circleBack : .otherCircleBack)
                    .onTapGesture { delta += 1 }
                
                Toggle(audioManager.currentNoteName, isOn: $audioManager.isPlaying)
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
                    .onTapGesture {
                        toggle = !toggle
                    }
                    .onChange(of: toggle) {
                        if toggle {audioManager.toggleDrone()}
                        toggle = false
                    }
                    .toggleStyle(.encircled)
                
                Text(audioManager.nextNoteName)
                    .encircle(diameter: 104,
                              textColor: audioManager.sequenceOrder == .forward ? .circleText : .otherCircleText,
                              circleColor: audioManager.sequenceOrder == .forward ? .circleBack : .otherCircleBack)
                    .onTapGesture { delta -= 1 }
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
        }
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
