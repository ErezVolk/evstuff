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
    func encircle(diameter: Int = 104, shadowRadius: CGFloat = 3, circleColor: Color = .gray) -> some View {
        font(.system(size: CGFloat(diameter / 4)))
            .foregroundColor(.white)
            .modifier(Encircled(diameter: CGFloat(diameter)))
            .shadow(radius: shadowRadius)
            .foregroundColor(circleColor)
    }
}

struct CircledToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .encircle(diameter: 128, shadowRadius: configuration.isOn ? 10: 3, circleColor: configuration.isOn ? Color.black : Color.gray)
    }
}

extension ToggleStyle where Self == CircledToggleStyle {
    static var encircled: CircledToggleStyle { .init() }
}
