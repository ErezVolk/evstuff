// Created by Erez Volk.

import SwiftUI
import Combine

enum Instrument: String, CaseIterable, Identifiable {
    case strings = "Strings"
    case beep = "Beep"
    var id: String { self.rawValue }
}

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @FocusState private var focused: Bool
    /// How much to add to the current note index on right arrow, meaning "forward"
    @State private var direction = 1
    // Since calling `audioManager` from `.onKeyPress` issues errors, save them aside
    @State private var toChangeNote = 0
    // Since calling `audioManager` from `.onTap` issues errors, save them aside
    @State private var toToggleDrone = false
#if os(macOS)
    private let signpostDiameter = 32
#else
    private let signpostDiameter = 40
    @State private var instrument: Instrument = .beep
#endif

    /// The "previous tone" circle
    var leftButton: some View {
        Text(audioManager.previousNoteName)
            .encircle(
                diameter: 80,
                shadowRadius: direction > 0 ? 3 : 6,
                textColor: direction > 0 ? .otherCircleText : .circleText,
                circleColor: direction > 0 ? .otherCircleBack : .circleBack)
    }

    /// The "next tone" circle
    var rightButton: some View {
        Text(audioManager.nextNoteName)
            .encircle(diameter: 80,
                      shadowRadius: direction > 0 ? 6 : 3,
                      textColor: direction > 0 ? .circleText : .otherCircleText,
                      circleColor: direction > 0 ? .circleBack : .otherCircleBack)
    }

    /// The "current tone" circle and keyboard event receiver
    var middleButton: some View {
        Toggle(audioManager.currentNoteName, isOn: $audioManager.isPlaying)
            .focusable()
            .focused($focused)
            .onAppear { focused = true }
            .toggleStyle(EncircledToggleStyle())
    }

    /// The sequence type (circle of fourths, etc.) picker
    var sequencePicker: some View {
        Picker("", selection: $selectedSequence) {
            ForEach(SequenceType.allCases) { sequence in
                Text(sequence.rawValue).tag(sequence)
            }
        }
#if os(macOS)
        .pickerStyle(.segmented)
#endif
        .fixedSize()
    }
    
    var instrumentPanel: some View {
#if os(macOS)
            HStack {
                Button("Load SoundFont") {
                    let panel = NSOpenPanel()
                    panel.allowsMultipleSelection = false
                    panel.canChooseDirectories = false
                    if panel.runModal() == .OK {
                        audioManager.loadInstrument(panel.url!)
                    }
                }
                Button(Instrument.strings.rawValue) {
                    audioManager.loadInstrument()
                }
                Button(Instrument.beep.rawValue) {
                    audioManager.resetInstrument()
                }
                
                Text(audioManager.instrument)
                    .monospaced()
            }
#else
            Picker("Instrument", selection: $instrument) {
                ForEach(Instrument.allCases) { instrument in
                    Text(instrument.rawValue).tag(instrument)
                }
            }
            .pickerStyle(.segmented)
            .fixedSize()
            .onChange(of: instrument) {
                switch (instrument) {
                case .strings: audioManager.loadInstrument()
                case .beep: audioManager.resetInstrument()
                }
            }
#endif
    }

    /// The "which way" button
    var signpost: some View {
        Image(systemName: direction > 0 ? "signpost.right.fill" : "signpost.left.fill")
            .encircle(diameter: signpostDiameter,
                      textColor: .directionText,
                      circleColor: .directionBack,
                      textFont: .body)
    }

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                leftButton
                    .onTapGesture { toChangeNote -= 1 }

                middleButton
                    .onKeyPress(keys: [.leftArrow]) { _ in
                        toChangeNote -= direction
                        return .handled
                    }
                    .onKeyPress(keys: [.rightArrow]) { _ in
                        toChangeNote += direction
                        return .handled
                    }
                    .onKeyPress(keys: [.space]) { _ in
                        toToggleDrone = !toToggleDrone
                        return .handled
                    }
                    .onTapGesture { toToggleDrone = !toToggleDrone }

                rightButton
                    .onTapGesture { toChangeNote += 1 }
            }

            HStack {
                sequencePicker

                signpost
                    .onTapGesture { direction = -direction }
            }

            instrumentPanel
        }
        .onChange(of: toToggleDrone) {
            if toToggleDrone {audioManager.toggleDrone()}
            toToggleDrone = false
        }
        .onChange(of: toChangeNote) {
            if toChangeNote != 0 { audioManager.changeDrone(toChangeNote) }
            toChangeNote = 0
        }
        .onChange(of: selectedSequence) {
            audioManager.sequenceType = selectedSequence
            audioManager.loadSequence()
        }
#if os(iOS)
        .containerRelativeFrame([.horizontal, .vertical])
        .background(Color.dronerooBack)
#endif
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
