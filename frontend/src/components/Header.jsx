import { motion, AnimatePresence } from 'framer-motion'

const Header = ({ onReset, showReset }) => {
  return (
    <motion.header
      className="border-b border-white/10 glass-effect"
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
    >
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-between">
          {/* Logo Section */}
          <motion.div
            className="flex items-center space-x-4"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            {/* Logo Placeholder - Sophisticated Circle with N */}
            <div className="relative">
              <motion.div
                className="w-12 h-12 rounded-full bg-gradient-to-br from-luxury-gold to-luxury-lightGold flex items-center justify-center shadow-lg"
                whileHover={{ scale: 1.05, rotate: 5 }}
                transition={{ type: "spring", stiffness: 400 }}
              >
                <span className="text-2xl font-serif font-bold text-luxury-navy">N</span>
              </motion.div>
              <motion.div
                className="absolute inset-0 rounded-full bg-gradient-to-br from-luxury-gold to-luxury-lightGold opacity-50 blur-md"
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.5, 0.3, 0.5],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            </div>

            <div>
              <h1 className="text-2xl font-serif font-bold gradient-text">
                Nomada
              </h1>
              <p className="text-sm text-luxury-cream/70 font-light">
                Your AI Travel Companion
              </p>
            </div>
          </motion.div>

          {/* Slogan and Reset Button */}
          <div className="flex items-center gap-6">
            {/* Slogan */}
            <motion.div
              className="hidden md:block"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
            >
              <p className="text-luxury-cream/80 font-serif italic text-lg">
                Where Intelligence Meets <span className="gradient-text">Wanderlust</span>
              </p>
            </motion.div>

            {/* Reset Button */}
            <AnimatePresence>
              {showReset && (
                <motion.button
                  onClick={onReset}
                  className="flex items-center gap-2 px-4 py-2 glass-effect rounded-full hover:bg-white/10 transition-all duration-300 border border-luxury-gold/30"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <svg
                    className="w-4 h-4 text-luxury-gold"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 19l-7-7m0 0l7-7m-7 7h18"
                    />
                  </svg>
                  <span className="text-luxury-cream/80 text-sm font-medium">New Chat</span>
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.header>
  )
}

export default Header
