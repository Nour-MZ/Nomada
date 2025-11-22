# Nomada - Luxury AI Travel Interface

A sophisticated, luxury-designed chat interface for Nomada, an AI-powered agentic travel system. This frontend serves as a cover/landing page that will eventually connect to a backend API.

## Design Philosophy

- **Modern Luxury Aesthetic**: Deep navy blues combined with elegant gold accents create a premium, trustworthy feel
- **Sophisticated UX**: Smooth animations and transitions throughout enhance the user experience
- **Unique Chat Design**: Distinctive hexagonal-inspired inbox design with decorative accents
- **Fully Responsive**: Beautiful on all screen sizes

## Color Scheme

- **Primary**: Deep Navy (#0A1628) - Professional, trustworthy base
- **Secondary**: Dark Blue (#1A2B47) - Depth and sophistication
- **Accent**: Gold (#D4AF37) - Luxury and warmth
- **Complementary**: Rose (#C9A9A6) - Warmth and elegance
- **Text**: Cream (#FAF9F6) - Easy on the eyes

## Key Features

### 1. **Elegant Header**
- Animated logo with subtle glow effect
- Company name with gradient text
- Compelling slogan: "Where Intelligence Meets Wanderlust"

### 2. **Welcome Section**
- Warm, inviting introduction to Nomada
- Feature cards highlighting key capabilities
- Smooth entrance animations

### 3. **Unique Chat Interface**
- Distinctive input design with decorative corner accents
- Hexagonal-inspired styling (not a standard rectangular box)
- Glowing effects and smooth animations
- Typing indicator with bouncing dots animation
- Clear distinction between user and AI messages

### 4. **Suggested Questions**
- 5 engaging example prompts showcasing capabilities:
  - Luxury honeymoon destinations
  - Budget-conscious European travel
  - Hidden gems in Southeast Asia
  - Adventure hiking destinations
  - Cultural culinary tours
- Click-to-ask functionality
- Categorized badges (Luxury, Budget-Conscious, Discovery, etc.)

### 5. **Smart Message System**
- Context-aware AI responses
- Message timestamps
- Smooth message animations
- Auto-scroll to latest message
- Welcome section hides after first message

## Tech Stack

- **React 18** - Modern UI library
- **Vite** - Fast build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Smooth animations and transitions
- **Google Fonts** - Cormorant Garamond (serif) & Inter (sans-serif)

## Setup Instructions

### Prerequisites
- Node.js (v18 or higher)
- npm or yarn

### Installation

1. Navigate to the frontend(2) directory:
```bash
cd frontend(2)
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser to `http://localhost:3001`

### Build for Production

```bash
npm run build
```

The production-ready files will be in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend(2)/
├── src/
│   ├── components/
│   │   ├── Header.jsx              # Logo, branding, slogan
│   │   ├── Welcome.jsx             # Welcome message & feature cards
│   │   ├── ChatInterface.jsx       # Unique chat input design
│   │   └── SuggestedQuestions.jsx  # Example question prompts
│   ├── App.jsx                     # Main application component
│   ├── main.jsx                    # Application entry point
│   └── index.css                   # Global styles & utilities
├── index.html                      # HTML template
├── vite.config.js                  # Vite configuration
├── tailwind.config.js              # Tailwind CSS configuration
├── postcss.config.js               # PostCSS configuration
└── package.json                    # Dependencies and scripts
```

## Demo Features

Currently, the application runs in **demo mode** with:
- Simulated AI responses based on user input keywords
- Mock typing indicators
- Context-aware reply generation
- Beautiful UI/UX demonstrating the final product vision

## Future Integration

This interface is designed to easily integrate with a backend API. Key integration points:

1. Replace `generateAIResponse()` function with actual API calls
2. Add authentication system
3. Connect to real travel data sources
4. Implement user profile and preferences
5. Add booking capabilities

## Customization

### Color Scheme
Edit `tailwind.config.js` to customize the luxury color palette:
```javascript
colors: {
  luxury: {
    navy: '#0A1628',
    gold: '#D4AF37',
    // ... more colors
  }
}
```

### Fonts
Modify the Google Fonts link in `index.html` and update `tailwind.config.js`:
```javascript
fontFamily: {
  serif: ['Cormorant Garamond', 'serif'],
  sans: ['Inter', 'sans-serif'],
}
```

### Suggested Questions
Update the `questions` array in `src/components/SuggestedQuestions.jsx`

## Performance

- Code splitting with Vite
- Optimized animations with Framer Motion
- Lazy loading of components where applicable
- CSS purging in production builds

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

Proprietary - Nomada AI Travel System

## Contact

For questions or support regarding this interface, please contact the development team.

---

**Nomada** - Where Intelligence Meets Wanderlust ✨
