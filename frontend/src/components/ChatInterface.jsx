import { motion } from 'framer-motion'

const ChatInterface = ({ inputValue, setInputValue, onSendMessage, isTyping }) => {
  const handleSubmit = (e) => {
    e.preventDefault()
    onSendMessage(inputValue)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSendMessage(inputValue)
    }
  }

  return (
    <motion.div
      className="w-full max-w-3xl mx-auto px-4"
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.5, duration: 0.6 }}
    >
      {/* Unique inbox design - Hexagonal inspired */}
      <div className="relative">
        {/* Glow effect */}
        <motion.div
          className="absolute -inset-1 bg-gradient-to-r from-luxury-gold/20 via-luxury-rose/20 to-luxury-gold/20 rounded-3xl blur-xl"
          animate={{
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />

        {/* Main input container */}
        <div className="relative glass-effect rounded-3xl p-3 shadow-2xl">
          <form onSubmit={handleSubmit} className="flex items-center gap-3">
            {/* Input area */}
            <div className="flex-1 relative">
              {/* Decorative corner accents */}
              <div className="absolute -top-2 -left-2 w-4 h-4 border-l-2 border-t-2 border-luxury-gold/50 rounded-tl-lg" />
              <div className="absolute -top-2 -right-2 w-4 h-4 border-r-2 border-t-2 border-luxury-gold/50 rounded-tr-lg" />
              <div className="absolute -bottom-2 -left-2 w-4 h-4 border-l-2 border-b-2 border-luxury-gold/50 rounded-bl-lg" />
              <div className="absolute -bottom-2 -right-2 w-4 h-4 border-r-2 border-b-2 border-luxury-gold/50 rounded-br-lg" />

              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Where would you like to explore today?"
                disabled={isTyping}
                rows="1"
                className="w-full bg-luxury-darkBlue/50 text-luxury-cream placeholder-luxury-cream/40
                         border-2 border-luxury-gold/30 rounded-2xl px-4 py-3
                         focus:outline-none focus:border-luxury-gold/60 focus:ring-2 focus:ring-luxury-gold/20
                         transition-all duration-300 resize-none
                         disabled:opacity-50 disabled:cursor-not-allowed
                         font-light text-base"
                style={{
                  minHeight: '50px',
                  maxHeight: '150px',
                }}
              />
            </div>

            {/* Send button - Sophisticated design */}
            <motion.button
              type="submit"
              disabled={!inputValue.trim() || isTyping}
              className="relative group disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-luxury-gold to-luxury-lightGold rounded-xl blur-md opacity-75 group-hover:opacity-100 transition-opacity" />
              <div className="relative bg-gradient-to-r from-luxury-gold to-luxury-lightGold rounded-xl p-3 shadow-lg">
                <svg
                  className="w-5 h-5 text-luxury-navy transform rotate-45"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              </div>
            </motion.button>
          </form>

          {/* Character counter / helper text */}
          <motion.div
            className="mt-3 flex items-center justify-between text-xs text-luxury-cream/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
          >
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 bg-luxury-gold rounded-full animate-pulse" />
              Demo mode - Backend integration coming soon
            </span>
            <span>Press Enter to send</span>
          </motion.div>
        </div>

        {/* Decorative floating elements */}
        <motion.div
          className="absolute -right-4 -top-4 w-8 h-8 bg-luxury-gold/10 rounded-full blur-sm"
          animate={{
            y: [0, -10, 0],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <motion.div
          className="absolute -left-6 top-0 w-6 h-6 bg-luxury-rose/10 rounded-full blur-sm"
          animate={{
            y: [0, 10, 0],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.5
          }}
        />
      </div>
    </motion.div>
  )
}

export default ChatInterface
