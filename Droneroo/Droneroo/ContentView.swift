// Created by Erez Volk.

import SwiftUI
import Combine

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @FocusState private var focused: Bool
    /// How much to add to the current note index on right arrow, meaning "forward"
    @State private var quantum = 1
    // Since calling `audioManager` from `.onKeyPress` issues errors, save them aside
    @State private var toChangeNote = 0
    // Since calling `audioManager` from `.onTap` issues errors, save them aside
    @State private var toToggleDrone = false
#if os(macOS)
    private let signpostDiameter = 32
#else
    private let signpostDiameter = 40
#endif

    var leftButton: some View {
        Text(audioManager.previousNoteName)
            .encircle(
                diameter: 80,
                textColor: quantum > 0 ? .otherCircleText : .circleText,
                circleColor: quantum > 0 ? .otherCircleBack : .circleBack)
    }

    var rightButton: some View {
        Text(audioManager.nextNoteName)
            .encircle(diameter: 80,
                      textColor: quantum > 0 ? .circleText : .otherCircleText,
                      circleColor: quantum > 0 ? .circleBack : .otherCircleBack)
    }

    var middleButton: some View {
        Toggle(audioManager.currentNoteName, isOn: $audioManager.isPlaying)
            .focusable()
            .focused($focused)
            .onAppear { focused = true }
            .toggleStyle(EncircledToggleStyle())
    }

    var sequencePicker: some View {
        Picker("", selection: $selectedSequence) {
            ForEach(SequenceType.allCases) { sequence in
                Text(sequence.rawValue).tag(sequence)
            }
        }
        .fixedSize()
    }

    var signpost: some View {
        Image(systemName: quantum > 0 ? "signpost.right.fill" : "signpost.left.fill")
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
                        toChangeNote -= quantum
                        return .handled
                    }
                    .onKeyPress(keys: [.rightArrow]) { _ in
                        toChangeNote += quantum
                        return .handled
                    }
                    .onKeyPress(keys: [.space]) { _ in
                        toToggleDrone = !toToggleDrone
                        return .handled
                    }
                    .onTapGesture {
                        toToggleDrone = !toToggleDrone
                    }

                rightButton
                    .onTapGesture { toChangeNote += 1 }
            }
            .onChange(of: toToggleDrone) {
                if toToggleDrone {audioManager.toggleDrone()}
                toToggleDrone = false
            }
            .onChange(of: toChangeNote) {
                if toChangeNote != 0 { audioManager.changeDrone(toChangeNote) }
                toChangeNote = 0
            }

            HStack {
                sequencePicker
                    .onChange(of: selectedSequence) {
                        audioManager.sequenceType = selectedSequence
                        audioManager.loadSequence()
                    }

                signpost
                    .onTapGesture { quantum = -quantum }
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
#if os(iOS)
        .containerRelativeFrame([.horizontal, .vertical])
        .background(Color.dronerooBack)
#endif
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
