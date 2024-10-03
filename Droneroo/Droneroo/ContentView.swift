// Created by Erez Volk.

import SwiftUI
import Combine

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
                    .onTapGesture { direction = -direction }
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
