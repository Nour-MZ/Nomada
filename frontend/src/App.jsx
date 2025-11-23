import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Header from './components/Header'
import Welcome from './components/Welcome'
import ChatInterface from './components/ChatInterface'
import SuggestedQuestions from './components/SuggestedQuestions'
import Sidebar from './components/Sidebar'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [chats, setChats] = useState([])
  const [currentChatId, setCurrentChatId] = useState(null)
  const [inputValue, setInputValue] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef(null)

  // Get current chat
  const currentChat = chats.find(chat => chat.id === currentChatId)
  const messages = currentChat?.messages || []
  const showWelcome = !currentChat || messages.length === 0

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const generateChatTitle = (firstMessage) => {
    // Generate a simple title from the first message
    const words = firstMessage.split(' ').slice(0, 6)
    return words.join(' ') + (firstMessage.split(' ').length > 6 ? '...' : '')
  }

  const handleSendMessage = (messageText) => {
    if (!messageText.trim()) return

    let targetChatId = currentChatId

    // Create new chat if none exists
    if (!currentChatId) {
      const newChatId = Date.now()
      const newChat = {
        id: newChatId,
        title: generateChatTitle(messageText),
        messages: [],
        messageCount: 0,
        createdAt: new Date()
      }
      setChats(prev => [newChat, ...prev])
      setCurrentChatId(newChatId)
      targetChatId = newChatId
    }

    // Add user message
    const userMessage = {
      id: Date.now(),
      text: messageText,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }

    setChats(prev => prev.map(chat => {
      if (chat.id === targetChatId) {
        return {
          ...chat,
          messages: [...chat.messages, userMessage],
          messageCount: chat.messages.length + 1
        }
      }
      return chat
    }))

    setInputValue('')

    // Simulate AI typing and response
    setIsTyping(true)
    setTimeout(() => {
      const aiMessage = {
        id: Date.now() + 1,
        text: generateAIResponse(messageText),
        sender: 'ai',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }

      setChats(prev => prev.map(chat => {
        if (chat.id === targetChatId) {
          return {
            ...chat,
            messages: [...chat.messages, aiMessage],
            messageCount: chat.messages.length + 1
          }
        }
        return chat
      }))
      setIsTyping(false)
    }, 2000)
  }

  const generateAIResponse = (userInput) => {
    const responses = {
      default: "I'm Nomada, your AI travel companion. While this is a demo interface, I'm designed to help you craft unforgettable journeys tailored to your unique preferences. Soon, I'll be able to provide personalized destination recommendations, create detailed itineraries, and uncover hidden gems around the world. What type of adventure are you dreaming of?",
      greeting: "Welcome! I'm thrilled to help you plan your next adventure. Whether you're seeking luxury escapes, cultural immersion, or off-the-beaten-path experiences, I'm here to make your travel dreams a reality. What destination has been calling to you?",
      budget: "I understand the importance of making every dollar count while experiencing the extraordinary. I can help you discover amazing destinations and experiences that align with your budget, from hidden local gems to smart luxury options. What's your ideal budget range, and what type of experiences matter most to you?",
      luxury: "Exquisite taste deserves exceptional experiences. I specialize in curating bespoke luxury journeys featuring world-class accommodations, exclusive experiences, and impeccable service. From private island retreats to Michelin-starred culinary tours, let's craft something truly remarkable. What defines luxury for you?",
      adventure: "Adventure awaits! Whether it's scaling mountain peaks, diving pristine reefs, or traversing ancient trails, I'll help you find experiences that match your spirit. What type of adventure makes your heart race?",
      culture: "Cultural immersion is the soul of meaningful travel. I can guide you to authentic experiences, from traditional ceremonies to local artisan workshops, helping you connect deeply with the places you visit. Which cultures are you most curious about?"
    }

    const lowerInput = userInput.toLowerCase()

    if (lowerInput.includes('hello') || lowerInput.includes('hi')) return responses.greeting
    if (lowerInput.includes('budget') || lowerInput.includes('afford')) return responses.budget
    if (lowerInput.includes('luxury') || lowerInput.includes('premium')) return responses.luxury
    if (lowerInput.includes('adventure') || lowerInput.includes('thrill')) return responses.adventure
    if (lowerInput.includes('culture') || lowerInput.includes('local')) return responses.culture

    return responses.default
  }

  const handleQuestionClick = (question) => {
    handleSendMessage(question)
  }

  const handleNewChat = () => {
    setCurrentChatId(null)
    setInputValue('')
    setSidebarOpen(false)
  }

  const handleSelectChat = (chatId) => {
    setCurrentChatId(chatId)
    setSidebarOpen(false)
  }

  const handleReset = () => {
    handleNewChat()
  }

  return (
    <div className="h-screen bg-gradient-to-br from-luxury-navy via-luxury-darkBlue to-luxury-slate overflow-hidden flex flex-col">
      {/* Animated background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-20 left-10 w-72 h-72 bg-luxury-gold/5 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <motion.div
          className="absolute bottom-20 right-10 w-96 h-96 bg-luxury-rose/5 rounded-full blur-3xl"
          animate={{
            scale: [1.2, 1, 1.2],
            opacity: [0.2, 0.4, 0.2],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
      </div>

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        chats={chats}
        currentChatId={currentChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
      />

      {/* Main content */}
      <div className="relative z-10 flex flex-col h-full">
        <Header onReset={handleReset} showReset={messages.length > 0} />

        {/* Main chat area - fixed height, no scroll on container */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 max-w-4xl mx-auto w-full">
            <AnimatePresence mode="wait">
              {showWelcome && (
                <Welcome key="welcome" onQuestionClick={handleQuestionClick} />
              )}
            </AnimatePresence>

            {/* Chat Messages - scrollable area */}
            {!showWelcome && (
              <motion.div
                className="w-full flex-1 overflow-y-auto scrollbar-luxury space-y-6 pb-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                <AnimatePresence>
                  {messages.map((message) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 20, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.3 }}
                      className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`chat-bubble ${
                        message.sender === 'user'
                          ? 'bg-gradient-to-r from-luxury-gold to-luxury-lightGold text-luxury-navy'
                          : 'glass-effect text-luxury-cream'
                      }`}>
                        <p className="text-base leading-relaxed">{message.text}</p>
                        <p className={`text-xs mt-2 ${
                          message.sender === 'user' ? 'text-luxury-navy/60' : 'text-luxury-cream/50'
                        }`}>
                          {message.timestamp}
                        </p>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {/* Typing Indicator */}
                <AnimatePresence>
                  {isTyping && (
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex justify-start"
                    >
                      <div className="glass-effect chat-bubble">
                        <div className="flex items-center space-x-2">
                          <div className="flex space-x-1">
                            <motion.div
                              className="w-2 h-2 bg-luxury-gold rounded-full"
                              animate={{ y: [0, -8, 0] }}
                              transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
                            />
                            <motion.div
                              className="w-2 h-2 bg-luxury-gold rounded-full"
                              animate={{ y: [0, -8, 0] }}
                              transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
                            />
                            <motion.div
                              className="w-2 h-2 bg-luxury-gold rounded-full"
                              animate={{ y: [0, -8, 0] }}
                              transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }}
                            />
                          </div>
                          <span className="text-luxury-cream/70 text-sm">Nomada is thinking...</span>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div ref={messagesEndRef} />
              </motion.div>
            )}
          </div>

          {/* Chat Input - Fixed at bottom */}
          <div className="pb-8">
            <ChatInterface
              inputValue={inputValue}
              setInputValue={setInputValue}
              onSendMessage={handleSendMessage}
              isTyping={isTyping}
            />
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
