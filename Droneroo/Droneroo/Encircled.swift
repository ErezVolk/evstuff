//  Created by Erez Volk on 01/10/2024.

import SwiftUICore
import SwiftUI

struct Encircled: ViewModifier {
    let diameter: CGFloat

    func body(content: Content) -> some View {
        return Circle()
            .frame(width: diameter, height: diameter)
            .overlay { content }
    }
}

extension View {
    func encircle(diameter: Int = 104,
                  shadowRadius: CGFloat = 3,
                  textColor: Color = .circleText,
                  circleColor: Color = .circleBack,
                  textFont: Font? = nil) -> some View {
        font(textFont ?? .system(size: CGFloat(diameter / 4)))
            .foregroundColor(textColor)
            .modifier(Encircled(diameter: CGFloat(diameter)))
            .shadow(radius: shadowRadius)
            .foregroundColor(circleColor)
    }
}

struct EncircledToggleStyle: ToggleStyle {
    var diameter = 128
    var onRadius: CGFloat = 10
    var offRadius: CGFloat = 3
    var textFont: Font?

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .encircle(
                diameter: self.diameter,
                shadowRadius: configuration.isOn ? onRadius: offRadius,
                textColor: configuration.isOn ? .onToggleText : .offToggleText,
                circleColor: configuration.isOn ? .onToggleBack : .offToggleBack,
                textFont: self.textFont)
    }
}
