class genericFEC:

      def _wrapDifference(self, current, previous, max):
          if previous > current:
              correction = current + max
              difference = correction - previous
          else:
              difference = current - previous
          return difference

      def __init__(self):

          self.pastElapsed = 0
          self.currentElapsed = 0
          self.pastTraveled = 0
          self.currentTraveled = 0
          self.mps = 0
          self.elapsedTime = 0
          self.distanceTraveled = 0
          self.speed = 0.0
          self.dataPageNumber = 0

      def p16(self, data):
          self.dataPageNumber = data[0]
          if(self.dataPageNumber == 16):
             self.currentElapsed = data[2]
             self.currentTraveled = data[3]
             self.mps = data[4] + (256 * data[5])
             if (self.mps == 65555):                                                                    # FFFF invalid
                 self.mps = 0

          self.elapsedTime += self._wrapDifference(self.currentElapsed, self.pastElapsed, 255) / 4      # seconds
          self.pastElapsed = self.currentElapsed
          self.distanceTraveled += self._wrapDifference(self.currentTraveled, self.pastTraveled, 255)   # meters
          self.pastTraveled = self.currentTraveled
          self.speed = self.mps * 0.0036                                                                # millimeters per second to Km/h