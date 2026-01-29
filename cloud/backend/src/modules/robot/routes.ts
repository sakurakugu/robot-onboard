import { Router } from 'express';
import { RobotController } from './controller';

export function createRobotRoutes(controller: RobotController): Router {
  const router = Router();

  router.get('/', controller.getAllRobots.bind(controller));
  router.get('/groups', controller.getGroups.bind(controller));
  router.get('/:uuid', controller.getRobot.bind(controller));
  router.post('/', controller.createRobot.bind(controller));
  router.put('/:uuid', controller.updateRobot.bind(controller));
  router.delete('/:uuid', controller.deleteRobot.bind(controller));
  router.post('/:uuid/test-connection', controller.testConnection.bind(controller));
  router.post('/:uuid/connect', controller.connectRobot.bind(controller));
  router.post('/:uuid/update-firmware', controller.updateFirmware.bind(controller));
  router.get('/:uuid/logs/history', controller.getLogHistory.bind(controller));
  router.post('/:uuid/logs/upload', controller.uploadLog.bind(controller));

  return router;
}
