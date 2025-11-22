import { motion } from 'framer-motion'

const Welcome = ({ onQuestionClick }) => {
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
    <div className="w-full max-w-3xl mx-auto text-center space-y-6">
      {/* Decorative element */}
      <motion.div
        className="flex justify-center mb-2"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
      >
        <div className="w-16 h-1 bg-gradient-to-r from-transparent via-luxury-gold to-transparent" />
      </motion.div>

      {/* Main heading */}
      <motion.h2
        className="text-4xl md:text-5xl font-serif font-bold"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <span className="gradient-text">Welcome, Traveler</span>
      </motion.h2>

      {/* Simple description */}
      <motion.p
        className="text-base text-luxury-cream/70 max-w-2xl mx-auto"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        I'm <span className="text-luxury-gold font-medium">Nomada</span>, your AI travel companion.
        I create personalized journeys, discover hidden gems, and craft unforgettable experiences
        tailored just for you.
      </motion.p>

      {/* Suggested Questions */}
      <motion.div
        className="pt-2"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <h3 className="text-luxury-cream/60 text-sm font-medium mb-3">
          Get started with a suggestion
        </h3>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {questions.map((question, index) => (
            <motion.button
              key={index}
              onClick={() => onQuestionClick(question.text)}
              className="group relative overflow-hidden glass-effect rounded-xl p-4 text-left
                       hover:bg-white/10 transition-all duration-300 border border-luxury-gold/20"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 + index * 0.08 }}
              whileHover={{ scale: 1.02, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              {/* Content */}
              <div className="relative z-10">
                {/* Icon and category */}
                <div className="flex items-start justify-between mb-2">
                  <span className="text-2xl">{question.icon}</span>
                  <span className="px-2 py-0.5 bg-luxury-gold/20 text-luxury-gold text-xs rounded-full
                               border border-luxury-gold/30 font-medium">
                    {question.category}
                  </span>
                </div>

                {/* Question text */}
                <p className="text-luxury-cream/90 text-sm leading-relaxed">
                  {question.text}
                </p>
              </div>
            </motion.button>
          ))}
        </div>
      </motion.div>

      {/* Bottom hint */}
      <motion.p
        className="text-luxury-cream/40 text-xs pt-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.0 }}
      >
        Or type your own message below to begin
      </motion.p>
    </div>
  )
}

export default Welcome
