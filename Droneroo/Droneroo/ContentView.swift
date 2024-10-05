// Created by Erez Volk.

import SwiftUI
import Combine

enum Instrument: String, CaseIterable, Identifiable {
    case strings = "Strings"
    case beep = "Beep"
    var id: String { self.rawValue }
}

extension View {
    /// Convenience wrapper around `.onKeyPress` so action can be a one-liner.
    func handleKey(_ key: KeyEquivalent, action: @escaping () -> Void) -> some View {
        return self.onKeyPress(key) {
            action()
            return .handled
        }
    }
}

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @FocusState private var focused: Bool
    /// How much to add to the current note index when the right arrow key is pressed ("forward")
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

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                prevNextButton(text: audioManager.previousNoteName, cond: direction < 0)
                    .onTapGesture { toChangeNote -= 1 }

                middleButton
                    .handleKey(.leftArrow) { toChangeNote -= direction }
                    .handleKey(.rightArrow) { toChangeNote += direction }
                    .handleKey(.space) { toToggleDrone = !toToggleDrone }
                    .onTapGesture { toToggleDrone = !toToggleDrone }

                prevNextButton(text: audioManager.nextNoteName, cond: direction > 0)
                    .onTapGesture { toChangeNote += 1 }
            }

            HStack {
                sequencePicker

                signpost
                    .onTapGesture { direction = -direction }
            }

            instrumentPanel
        }
        .onAppear {
            audioManager.loadSequence()
        }
        .onChange(of: toToggleDrone) {
            if toToggleDrone { audioManager.toggleDrone() }
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
        .background(.dronerooBack)
#endif
    }

    /// The "previous/next tone" circles
    func prevNextButton(text: String, cond: Bool) -> some View {
        return Text(text)
            .encircle(
                diameter: 80,
                shadowRadius: cond ? 6 : 3,
                textColor: cond ? .circleText : .otherCircleText,
                circleColor: cond ? .circleBack : .otherCircleBack)
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

    /// Selection of MIDI instrument to play
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
                switch instrument {
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
}
