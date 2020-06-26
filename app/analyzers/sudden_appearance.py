from helpers.singletons import settings, es, logging
from helpers.analyzer import Analyzer
import datetime as dt
import dateutil.parser


class SuddenAppearanceAnalyzer(Analyzer):

    def __init__(self, model_name, config_section):
        super(SuddenAppearanceAnalyzer, self).__init__("sudden_appearance", model_name, config_section)

    def _extract_additional_model_settings(self):
        """
        Override method from Analyzer
        """
        self.model_settings["timestamp_field"] = settings.config.get("general",
                                                                     "timestamp_field",
                                                                     fallback="@timestamp")

        self.model_settings["target"] = self.config_section["target"].replace(' ', '').split(",")
        self.model_settings["aggregator"] = self.config_section["aggregator"].replace(' ', '').split(",")

        self.model_settings["slide_window_days"] = self.config_section.getint("slide_window_days")
        self.model_settings["slide_window_hours"] = self.config_section.getint("slide_window_hours")
        self.model_settings["slide_window_mins"] = self.config_section.getint("slide_window_mins", fallback=0)
        self.model_settings["slide_jump_days"] = self.config_section.getint("slide_jump_days")
        self.model_settings["slide_jump_hours"] = self.config_section.getint("slide_jump_hours")
        self.model_settings["slide_jump_mins"] = self.config_section.getint("slide_jump_mins")

        self.model_settings["trigger_slide_window_proportion"] = self.config_section.getfloat(
            "trigger_slide_window_proportion")

        self.delta_history_win = dt.timedelta(days=self.model_settings["history_window_days"],
                                              hours=self.model_settings["history_window_hours"])

        self.delta_slide_win = dt.timedelta(days=self.model_settings["slide_window_days"],
                                            hours=self.model_settings["slide_window_hours"],
                                            minutes=self.model_settings["slide_window_mins"])

        self.jump_win = dt.timedelta(days=self.model_settings["slide_jump_days"],
                                     hours=self.model_settings["slide_jump_hours"],
                                     minutes=self.model_settings["slide_jump_mins"])

        if self.delta_history_win < self.delta_slide_win:
            raise ValueError("Slide window of size %s is bigger than history window of size %s" % (
                self.delta_slide_win, self.delta_history_win))

        if self.delta_slide_win < self.jump_win:
            raise ValueError("Jump window of size %s is bigger than slide window of size %s" % (
                self.jump_win, self.delta_slide_win))

    def evaluate_model(self):
        if self.model_settings["test_model"]:
            end_time = dt.datetime(year=2020, month=4, day=23, hour=15, minute=30)
        else:
            end_time = dt.datetime.now()
        start_slide_win = end_time - self.delta_history_win
        end_slide_win = start_slide_win + self.delta_slide_win

        while end_slide_win < end_time:
            self.find_sudden_appearance(start_slide_win, end_slide_win)
            start_slide_win += self.jump_win
            end_slide_win += self.jump_win
            if end_slide_win >= end_time:
                end_slide_win = end_time
                start_slide_win = end_time - self.jump_win
                self.find_sudden_appearance(start_slide_win, end_slide_win)

        self.print_analysis_summary()

    def find_sudden_appearance(self, start_slide_win, end_slide_win):
        aggregation_buckets = es.scan_first_occur_documents(search_query=self.search_query,
                                                            start_time=start_slide_win,
                                                            end_time=end_slide_win,
                                                            model_settings=self.model_settings)
        for bucket in aggregation_buckets:
            bucket_docs = bucket["target"]["buckets"]
            for doc in bucket_docs:
                raw_doc = doc["top_doc"]["hits"]["hits"][0]
                fields = es.extract_fields_from_document(raw_doc,
                                                         extract_derived_fields=self.model_settings[
                                                             "use_derived_fields"])

                event_timestamp = dateutil.parser.parse(fields[self.model_settings["timestamp_field"]],
                                                        ignoretz=True)
                prop_time_win_event_appears = (event_timestamp - start_slide_win) / (end_slide_win - start_slide_win)
                if prop_time_win_event_appears > self.model_settings["trigger_slide_window_proportion"]:
                    extra_outlier_information = dict()
                    extra_outlier_information["prop_first_appear_in_time_window"] = prop_time_win_event_appears
                    trigger_slide_window_proportion_str = str(self.model_settings["trigger_slide_window_proportion"])
                    extra_outlier_information["trigger_slide_window_proportion"] = trigger_slide_window_proportion_str
                    extra_outlier_information["size_time_window"] = str(self.delta_slide_win)
                    extra_outlier_information["start_time_window"] = str(start_slide_win)
                    extra_outlier_information["end_time_window"] = str(end_slide_win)
                    extra_outlier_information["aggregator"] = self.model_settings["aggregator"]
                    extra_outlier_information["aggregator_value"] = bucket["key"]
                    extra_outlier_information["target"] = self.model_settings["target"]
                    extra_outlier_information["target_value"] = doc["key"]
                    extra_outlier_information["resume"] = "In aggregator '" + \
                                                          ", ".join(self.model_settings["aggregator"]) + \
                                                          ": " + bucket["key"] + \
                                                          "', the field(s) '" + \
                                                          " ,".join(self.model_settings["target"]) + \
                                                          ": " + doc["key"] + \
                                                          "' appear(s) suddently at " + \
                                                          "{:.2}".format(prop_time_win_event_appears) + \
                                                          "/1 of the time window of size " + \
                                                          str(self.model_settings["slide_window_days"]) + " days " + \
                                                          str(self.model_settings["slide_window_hours"]) + " hours " + \
                                                          str(self.model_settings["slide_window_mins"]) + " mins "

                    outlier = self.create_outlier(fields,
                                                  raw_doc,
                                                  extra_outlier_information=extra_outlier_information)

                    logging.logger.debug(outlier)
                    self.process_outlier(outlier)
