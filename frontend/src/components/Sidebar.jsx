import { motion, AnimatePresence } from 'framer-motion'

const Sidebar = ({ isOpen, setIsOpen, chats, currentChatId, onNewChat, onSelectChat }) => {
  return (
    <>
      {/* Toggle Button - Always visible */}
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 p-2 glass-effect rounded-lg hover:bg-white/10 transition-all duration-300 border border-luxury-gold/30"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <svg
          className="w-5 h-5 text-luxury-gold"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          {isOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </motion.button>

      {/* Sidebar */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            exit={{ x: -300 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed left-0 top-0 h-full w-64 glass-effect border-r border-luxury-gold/20 z-40 flex flex-col"
          >
            {/* Header */}
            <div className="p-6 pt-20 border-b border-luxury-gold/20">
              <h2 className="text-luxury-gold font-serif text-xl font-bold mb-4">Nomada</h2>

              {/* New Chat Button */}
              <motion.button
                onClick={onNewChat}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-luxury-gold to-luxury-lightGold text-luxury-navy rounded-xl font-medium hover:shadow-lg transition-all duration-300"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Chat
              </motion.button>
            </div>

            {/* Chats List */}
            <div className="flex-1 overflow-y-auto scrollbar-luxury p-4">
              <h3 className="text-luxury-cream/60 text-sm font-medium mb-3 px-2">Chat History</h3>

              {chats.length === 0 ? (
                <p className="text-luxury-cream/40 text-sm px-2 italic">No previous chats</p>
              ) : (
                <div className="space-y-2">
                  {chats.map((chat) => (
                    <motion.button
                      key={chat.id}
                      onClick={() => onSelectChat(chat.id)}
                      className={`w-full text-left px-3 py-2 rounded-lg transition-all duration-200 ${
                        currentChatId === chat.id
                          ? 'bg-luxury-gold/20 border border-luxury-gold/40'
                          : 'hover:bg-white/5 border border-transparent'
                      }`}
                      whileHover={{ x: 4 }}
                    >
                      <p className={`text-sm truncate ${
                        currentChatId === chat.id ? 'text-luxury-gold' : 'text-luxury-cream/80'
                      }`}>
                        {chat.title}
                      </p>
                      <p className="text-xs text-luxury-cream/40 mt-1">
                        {chat.messageCount} message{chat.messageCount !== 1 ? 's' : ''}
                      </p>
                    </motion.button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-luxury-gold/20">
              <p className="text-luxury-cream/40 text-xs text-center">
                AI Travel Companion
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Overlay when sidebar is open */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-black/50 z-30 md:hidden"
          />
        )}
      </AnimatePresence>
    </>
  )
}

export default Sidebar
