import numpy as np
import cv2, time
from os import path
from matplotlib import pyplot as plt
import time

from PIL import Image

import gym
from gym import spaces
from gym.utils import seeding

from pseudoslam.envs.simulator.pseudoSlam import pseudoSlam

class RobotExplorationT0(gym.Env):
    def __init__(self, config_path='dataset_config.yaml'):
        if config_path.startswith("/"):
            fullpath = config_path
        else:
            fullpath = path.join(path.dirname(__file__), "config", config_path)
        if not path.exists(fullpath):
            raise IOError("File %s does not exist" % fullpath)

        self.sim = pseudoSlam(fullpath)
        self.action_space = self._get_action_space()
        self.observation_space = self._get_observation_space()
        self.last_map = self.sim.get_state()
        self.last_action = None

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def render(self, mode='human'):
        slamMap = self._get_obs()[:,:,0]
        if mode == "human":
            plt.figure(0)
            plt.clf()
            plt.imshow(slamMap, cmap='gray') #show POV view
            plt.draw()
            plt.pause(0.00001)
        elif mode == "rgb_array":
            obs = np.expand_dims(slamMap, -1).repeat(3, -1)
            obs += 101  # convert to [0,255]
            obs = obs.astype(np.uint8)
            return obs

    def reset(self, order=True):
        self.sim.reset(order)
        self.last_map = self.sim.get_state()
        self.last_action = None
        return self._get_obs()

    def step(self, action):
        action = int(action)
        assert action in [0, 1, 2]
        action = ['forward', 'left', 'right'][action]
        crush_flag = self.sim.moveRobot(action)

        obs = self._get_obs()
        reward = self._compute_reward(crush_flag, action)
        done = (self.sim.measure_ratio() > 1)
        print("Map completion : " + str(self.sim.measure_ratio()), end='\r')
        info = {'is_success': done}

        return obs, reward, done, info


    def close(self):
        pass

    def _compute_reward(self, crush_flag, action):
        """Recurn the reward"""
        current_map = self.sim.get_state()
        difference_map = np.sum(self.last_map == self.sim.map_color['uncertain'])\
                         - np.sum(current_map == self.sim.map_color['uncertain'])
        self.last_map = current_map
        # exploration
        reward = (1. * difference_map / self.sim.m2p / self.sim.m2p)
        #print("Difference map: " +str(difference_map))
        #print("sim.m2p" + str(self.sim.m2p))
        #print(reward)
        return reward


    def _get_action_space(self):
        """Forward, left and right"""
        return spaces.Discrete(3)

    def _get_observation_space(self):
        obs = self._get_obs()
        observation_space = spaces.Box(-np.inf, np.inf, shape=obs.shape, dtype='float32')
        return observation_space

    def _get_obs(self):
        """
        """
        observation = self.sim.get_state()
        pose = self.sim.get_pose()

        (rot_y, rot_x) = (int(pose[0]), int(pose[1]))
        rot_theta = -pose[2] * 180. / np.pi + 90  # Upward

        # Pad boundaries
        pad_x, pad_y = int(self.sim.state_size[0]/2. * 1.5), int(self.sim.state_size[1]/2. * 1.5)
        state_size_x, state_size_y = int(self.sim.state_size[0]), int(self.sim.state_size[1])
        if rot_y - pad_y < 0:
            observation = cv2.copyMakeBorder(observation, top=pad_y, bottom=0, left=0, right=0,
                                             borderType=cv2.BORDER_CONSTANT, value=self.sim.map_color['obstacle'])
            rot_y += pad_y
        if rot_x - pad_x < 0:
            observation = cv2.copyMakeBorder(observation, top=0, bottom=0, left=pad_x, right=0,
                                             borderType=cv2.BORDER_CONSTANT, value=self.sim.map_color['obstacle'])
            rot_x += pad_x
        if rot_y + pad_y > observation.shape[0]:
            observation = cv2.copyMakeBorder(observation, top=0, bottom=pad_y, left=0, right=0,
                                             borderType=cv2.BORDER_CONSTANT, value=self.sim.map_color['obstacle'])
        if rot_x + pad_x > observation.shape[1]:
            observation = cv2.copyMakeBorder(observation, top=0, bottom=0, left=0, right=pad_x,
                                             borderType=cv2.BORDER_CONSTANT, value=self.sim.map_color['obstacle'])

        # Rotate global map and crop the local observation
        local_map = observation[rot_y - pad_y:rot_y + pad_y, rot_x - pad_x:rot_x + pad_x]
        M = cv2.getRotationMatrix2D((pad_y, pad_x), rot_theta, 1)
        dst = cv2.warpAffine(local_map, M, (pad_y*2, pad_x*2), flags=cv2.INTER_NEAREST,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=self.sim.map_color['obstacle'])
        dst = dst[pad_y - int(state_size_y/2.):pad_y + int(state_size_y/2.),
                  pad_x - int(state_size_x/2.):pad_x + int(state_size_x/2.)]
        dst = dst[:,:,np.newaxis]

        # Draw the robot at the center
        cv2.circle(dst, (int(state_size_y/2.), int(state_size_x/2.)), int(self.sim.robotRadius), 50, thickness=-1)
        cv2.rectangle(dst, (int(state_size_y/2.) - int(self.sim.robotRadius),
                            int(state_size_x/2.) - int(self.sim.robotRadius)),
                      (int(state_size_y / 2.) + int(self.sim.robotRadius),
                       int(state_size_x / 2.) + int(self.sim.robotRadius)),
                      50, -1)
        return dst.copy()


if __name__ == '__main__':
    env = RobotExplorationT0()
    env.reset()
    start_time = time.time()
    count = 0
    generation = 0
    epi_cnt = 0
    epi_max = 2000
    epi_list = [0]
    perc = 10
    total_images = 0

    #10% increments of total episode count
    for i in range (0,10):
       epi_list.append(epi_max / 10 + epi_list[i])



    while 1:

        pose = env.sim.get_pose()
        plt.figure(1, figsize=(2.56,2.56))#figure size 
        plt.clf()
        
        plt.imshow(env.sim.get_state().copy(), cmap='gray')
        plt.draw()
        plt.axis("off")
        plt.pause(0.00001)
        
        cGraph=plt.gcf()
        #env.render() #POV
        
        epi_cnt += 1
        act = np.random.randint(3)
        obs, reward, done, info = env.step(act)
        cmd = ['forward', 'left', 'right']
        
        if epi_cnt in epi_list:
            print("\n" + str(perc) + "% episodes used")
            perc = perc + 10
           # print(str(sim.measure_ratio) + "mapped")
        #change episode count 
        if epi_cnt > epi_max or done:
            finish_time = int(time.time() - start_time) 
            print("\n final episode : " +str(epi_cnt) + "/" +str(epi_max))
            plt.tight_layout()
            data = np.frombuffer(cGraph.canvas.tostring_rgb(), dtype=np.uint8)
            data = data.reshape(cGraph.canvas.get_width_height()[::-1] + (3,))
            im = Image.fromarray(np.uint8(data))
            im = im.resize((256,256)) #crop image
            im.save("images/HD"+"/image"+str(count)+".png")
           #cGraph.savefig("images/HD"+"/image"+str(count)+".png") #save the completed map
            print("Image : " +str(count) + " saved")
            print("Total sim time : " + str(finish_time) +" seconds")
            epi_cnt = 0
            count +=1
            total_images +=1 
            perc = 0 
            print("Total Images : " +str(total_images))
            env.reset()




