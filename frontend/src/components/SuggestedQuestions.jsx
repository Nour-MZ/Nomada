import { motion } from 'framer-motion'

const SuggestedQuestions = ({ onQuestionClick }) => {
  const questions = [
    {
      icon: '🌴',
      text: 'Suggest a tropical paradise for my honeymoon',
      category: 'Luxury'
    },
    {
      icon: '💰',
      text: 'Plan a 2-week European adventure under $3000',
      category: 'Budget-Conscious'
    },
    {
      icon: '🗺️',
      text: 'Show me hidden gems in Southeast Asia',
      category: 'Discovery'
    },
    {
      icon: '🏔️',
      text: 'Find the best hiking destinations for spring',
      category: 'Adventure'
    },
    {
      icon: '🍷',
      text: 'Create a culinary tour through Italy',
      category: 'Culture'
    }
  ]

  return (
    <motion.div
      className="mb-32"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 1.0 }}
    >
      <motion.div
        className="text-center mb-8"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2 }}
      >
        <h3 className="text-2xl font-serif text-luxury-cream/80 mb-2">
          Not sure where to start?
        </h3>
        <p className="text-luxury-cream/50">Try one of these suggestions</p>
      </motion.div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {questions.map((question, index) => (
          <motion.button
            key={index}
            onClick={() => onQuestionClick(question.text)}
            className="group relative overflow-hidden glass-effect rounded-2xl p-6 text-left
                     hover:bg-white/10 transition-all duration-300"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.3 + index * 0.1 }}
            whileHover={{ scale: 1.02, y: -4 }}
            whileTap={{ scale: 0.98 }}
          >
            {/* Hover gradient effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-luxury-gold/0 to-luxury-rose/0
                          group-hover:from-luxury-gold/10 group-hover:to-luxury-rose/10
                          transition-all duration-500 rounded-2xl" />

            {/* Content */}
            <div className="relative z-10">
              {/* Icon and category badge */}
              <div className="flex items-start justify-between mb-4">
                <motion.div
                  className="text-4xl"
                  whileHover={{ scale: 1.2, rotate: 10 }}
                  transition={{ type: "spring", stiffness: 400 }}
                >
                  {question.icon}
                </motion.div>
                <span className="px-3 py-1 bg-luxury-gold/20 text-luxury-gold text-xs rounded-full
                               border border-luxury-gold/30 font-medium">
                  {question.category}
                </span>
              </div>

              {/* Question text */}
              <p className="text-luxury-cream group-hover:text-luxury-lightGold
                          transition-colors duration-300 leading-relaxed">
                {question.text}
              </p>

              {/* Arrow indicator */}
              <motion.div
                className="mt-4 flex items-center text-luxury-gold/70 group-hover:text-luxury-gold text-sm"
                initial={{ x: 0 }}
                whileHover={{ x: 5 }}
              >
                <span>Ask this</span>
                <svg
                  className="w-4 h-4 ml-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </motion.div>
            </div>

            {/* Decorative corner accent */}
            <div className="absolute top-0 right-0 w-16 h-16 opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="absolute top-2 right-2 w-8 h-8 border-t-2 border-r-2 border-luxury-gold/30 rounded-tr-xl" />
            </div>
          </motion.button>
        ))}
      </div>

      {/* Decorative divider */}
      <motion.div
        className="flex justify-center mt-12"
        initial={{ opacity: 0, scaleX: 0 }}
        animate={{ opacity: 1, scaleX: 1 }}
        transition={{ delay: 2.0 }}
      >
        <div className="w-32 h-px bg-gradient-to-r from-transparent via-luxury-gold/50 to-transparent" />
      </motion.div>
    </motion.div>
  )
}

export default SuggestedQuestions
