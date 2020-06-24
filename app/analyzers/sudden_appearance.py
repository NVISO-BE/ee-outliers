from helpers.singletons import settings, es, logging
from helpers.analyzer import Analyzer


class SuddenAppearanceAnalyzer(Analyzer):

    def __init__(self, model_name, config_section):
        super(SuddenAppearanceAnalyzer, self).__init__("sudden_appearance", model_name, config_section)

    def _extract_additional_model_settings(self):
        """
        Override method from Analyzer
        """
        self.model_settings["slide_window_days"] = self.config_section.getint("slide_window_days")
        self.model_settings["slide_window_hours"] = self.config_section.getint("slide_window_hours")
        self.model_settings["slide_jump_days"] = self.config_section.getint("slide_jump_days")
        self.model_settings["slide_jump_hours"] = self.config_section.getint("slide_jump_hours")
        self.model_settings["slide_jump_mins"] = self.config_section.getint("slide_jump_mins")
        settings.config.get("simplequery", "highlight_match")
        logging.logger.debug("Parameters:")
        logging.logger.debug("slide_window_days: " + str(self.model_settings["slide_window_days"]))
        logging.logger.debug("slide_window_hours: " + str(self.model_settings["slide_window_hours"]))
        logging.logger.debug("slide_jump_days: " + str(self.model_settings["slide_jump_days"]))
        logging.logger.debug("slide_jump_hours: " + str(self.model_settings["slide_jump_hours"]))
        logging.logger.debug("slide_jump_mins: " + str(self.model_settings["slide_jump_mins"]))
        logging.logger.debug("history_window_days: " + str(self.model_settings["history_window_days"]))
        logging.logger.debug("history_window_hours: " + str(self.model_settings["history_window_hours"]))

    def evaluate_model(self):
        train_data = list()
        logging.logger.debug("flag1")
        self.total_events, documents = es.count_and_scan_first_occur_documents(index=self.model_settings["es_index"],
                                                                               search_query=self.search_query,
                                                                               model_settings=self.model_settings)

        total_training_events = int(self.total_events)

        logging.init_ticker(total_steps=total_training_events, desc=self.model_name + " - preparing training set")
        if self.total_events > 0:
            for doc in documents:
                if len(train_data) < 1:
                    logging.tick()
                    fields = es.extract_fields_from_document(
                        doc, extract_derived_fields=self.model_settings["use_derived_fields"])
                    logging.logger.debug(fields['host'])
                    logging.logger.debug(doc["_id"])
                    logging.logger.debug(fields["TimeCreated.SystemTime"])
                    logging.logger.debug(fields["@timestamp"])
                    train_data.append(fields)
                else:
                    # We have collected sufficient training data
                    break

        # Now, train the model
        if train_data:
            pass  # Train!!
        else:
            logging.logger.warning("no sentences to train model on. Are you sure the sentence configuration is " +
                                   "correctly defined?")

    def run_model(self):
        pass
