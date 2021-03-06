# -*- coding: utf-8 -*-
#BEGIN_HEADER
import os
import sys
import traceback
import uuid
import errno
import subprocess
from biokbase.workspace.client import Workspace as workspaceService
#from KBaseReport.KBaseReportClient import KBaseReport
from Weka.Utils.ReportUtil import ReportUtil
#END_HEADER


class Weka:
    '''
    Module Name:
    Weka

    Module Description:
    A KBase module: Weka
    '''

    ######## WARNING FOR GEVENT USERS ####### noqa
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    ######################################### noqa
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/mikacashman/Weka.git"
    GIT_COMMIT_HASH = "badbf5652d2cbf8427109c4c79f2e91a07f55d61"

    #BEGIN_CLASS_HEADER
    workspaceURL = None
    # Class variables and functions can be defined in this block

    def _mkdir_p(self, path):
        """
        _mkdir_p: make directory for given path
        """
        if not path:
            return
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise
    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.callbackURL = os.environ['SDK_CALLBACK_URL']
        self.config = config
        self.config['SDK_CALLBACK_URL'] = os.environ['SDK_CALLBACK_URL']
        self.config['KB_AUTH_TOKEN'] = os.environ['KB_AUTH_TOKEN']
        self.scratch = config['scratch']
        self.workspaceURL = config['workspace-url']
        if self.callbackURL is None:
            raise ValueError("SDK_CALLBACK_URL not set in environment")
        #END_CONSTRUCTOR
        pass

    def DecisionTree(self, ctx, params):
        """
        :param params: instance of type "DTParams" -> structure: parameter
           "workspace_name" of String, parameter "phenotype_ref" of String,
           parameter "confidenceFactor" of Double, parameter "minNumObj" of
           Long, parameter "numFolds" of Long, parameter "seed" of Long,
           parameter "unpruned" of type "bool" (A binary boolean), parameter
           "class_values" of String, parameter "class_labels" of String
        :returns: instance of type "DTOutput" -> structure: parameter
           "report_name" of String, parameter "report_ref" of String
        """
        # ctx is the context object
        # return variables are: output
        #BEGIN DecisionTree
        #runs J48 Deicison trees in weka on phenotype set

        ### STEP 1 - Parse input and catch any errors
        if 'workspace_name' not in params:
                raise ValueError('Parameter workspace is not set in input arguments')
        # workspace_name = params['workspace_name']
        if 'phenotype_ref' not in params:
                raise ValueError('Parameter phenotype is not set in input arguments')
        phenotype = params['phenotype_ref']
        if 'class_values' not in params:
                class_values = ["0", "1"]
        else:
                class_values = list(params['class_values'].split(","))
        if 'class_labels' not in params:
                class_labels = ["NO_GROWTH", "GROWTH"]
        else:
                class_labels = list(params['class_labels'].split(","))
        if len(class_values) != len(class_labels):
                raise ValueError('Class Values and Class Labels must have equal length,'
                                 ' each class seperated by a comma')

        ### STEP 2 - Get the input data
        token = ctx['token']
        wsClient = workspaceService(self.workspaceURL, token=token)
        try:
                pheno = wsClient.get_objects([{'ref': phenotype}])[0]['data']
        except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                orig_error = ''.join('   ' + line for line in lines)
                raise ValueError('Error loading original Phenotype object from workspace:\n'
                                 + orig_error)
        classes = dict(zip(class_values, class_labels))

        ### STEP 2.5 - Set up biochem data to get cpd name from ID
        biochem_ref = "kbase/default"
        biochem = wsClient.get_objects([{'ref': biochem_ref}])[0]['data']
        compound_name_dict = {}
        for cpd in biochem['compounds']:
                compound_name_dict[cpd['id']] = cpd['name']

        ### STEP 3 - Create Matrix
        #currently assumed the base media is the same for all phenotypes,
        #this should be updated later to allow more flexibility.
        phenos = []
        compounds = []
        growth = []

        for i in range(0, len(pheno['phenotypes'])):
                temp = []
                #zero out list first (no compounds present)
                for j in range(0, len(compounds)):
                        temp.append(0)
                for j in range(0, len(pheno['phenotypes'][i]['additionalcompound_refs'])):
                        if pheno['phenotypes'][i]['additionalcompound_refs'][j] in compounds:
                                #find it in the list and make it a 1
                                temp[compounds.index(pheno['phenotypes'][i]
                                                     ['additionalcompound_refs'][j])] = 1
                        else:
                                #add 0 to all exisiting phenos and add 1 to this one
                                compounds.append(pheno['phenotypes'][i]
                                                 ['additionalcompound_refs'][j])
                                for k in range(0, len(phenos)):
                                        phenos[k].append(0)
                                temp.append(1)
                phenos.append(temp)
                growth.append(pheno['phenotypes'][i]['normalizedGrowth'])
        #print("Compounds: ")
        #print(compounds)
        #print("Growth values: ")
        #print(growth)

        ### STEP test - Print matrix to file
        #this code is used for debugging to ensure the matrix is
        #created properly
        #matfilename = self.scratch + "/work/matrix.txt"
        #matrixfile = open(matfilename,"w+")
        #for i in range(0,len(compounds)):
        #       matrixfile.write(compounds[i] + " ")
        #matrixfile.write("\n")
        #for i in range(0,len(phenos)):
        #       for j in range(0,len(phenos[i])):
        #               matrixfile.write(str(phenos[i][j]))
        #       matrixfile.write(" --> " + str(growth[i]))
        #       matrixfile.write("\n")
        #matrixfile.close()

        ### STEP 4 - Create ARFF file
        #creates the .arff file which is input to Weka
        wekafile = self.scratch + "/weka.arff"
        arff = open(wekafile, "w+")
        arff.write("@RELATION J48DT_Phenotype\n\n")
        for i in range(0, len(compounds)):
                arff.write("@ATTRIBUTE " + compound_name_dict[compounds[i][-8:]].replace(" ", "_")
                           + " {ON,OFF}\n")
                #arff.write("@ATTRIBUTE " + compounds[i][-8:] + " {ON,OFF}\n")
        arff.write("@ATTRIBUTE class {")
        count = len(classes)
        temp = 0
        for key, value in classes.items():
                temp += 1
                if temp == count:
                        arff.write(value)
                else:
                        arff.write(value + ",")
        arff.write("}\n\n@data\n")
        for i in range(0, len(phenos)):
                for j in range(0, len(phenos[i])):
                        if phenos[i][j] == 1:
                                arff.write("ON,")
                        elif phenos[i][j] == 0:
                                arff.write("OFF,")
                        else:
                                raise ValueError("Error: Invalid compound in phenos associated"
                                                 " with phenotype."
                                                 "  Must be a 1 (for ON) or 0 (for OFF).")
                try:
                        arff.write(classes[str(growth[i])] + '\n')
                except:
                        raise ValueError('Class dictionary key error. Can\'t find class label for ',
                                         growth[i],
                                         ' Please check your Class Values/Labels mapping.')
        arff.close()

        ### STEP 5 - Send to WEKA
        #Call weka with a different protocol?  os.system not recomeneded - what is?
        #Need to account for invalid settings
        #TODO use Weka's built in - need to catch the Weka exception
        outfilename = self.scratch + "/weka.out"
        print(params)
        weka_params = ""
        if "unpruned" in params and params['unpruned'] is not None and params['unpruned'] == 1:
                weka_params += " -U"
        if "confidenceFactor" in params and params['confidenceFactor'] is not None:
            if params['confidenceFactor'] != "0.25":
                weka_params += " -C " + str(params['confidenceFactor'])
        if "minNumObj" in params and params['minNumObj'] is not None and params['minNumObj'] != "2":
                weka_params += " -M " + params['minNumObj']
        if "seed" in params and params['seed'] is not None and params['seed'] != "1":
                weka_params += " -s " + str(params['seed'])
        if "numFolds" in params and params['numFolds'] is not None and params['numFolds'] != "3":
                weka_params += " -x " + str(params['numFolds'])
        call = "java weka.classifiers.trees.J48 -t " + wekafile + weka_params \
            + " -i > " + outfilename
        print("Weka call is: " + call)
        try:
                os.system(call)
        except:
                print("EXCEPTION---------------------------------------")

        #Call weka again with graph output
        #Save -g output as .dot file for input to dot
        dotfilename = self.scratch + "/weka.dot"
        dotFile = open(dotfilename, 'w+')
        call_graph = "java weka.classifiers.trees.J48 -g -t " + wekafile + weka_params
        print(dotfilename)
        #BELOW - shell=True is strongly discouraged...
        try:
            subprocess.call(call_graph, stdout=dotFile, shell=True)
        except:
            print("EXCEPTION---------------------------------------")
        dotFile.close()
        #test print graph results
        tempFile = open(dotfilename, 'r')
        print(tempFile.read())
        tempFile.close()

        #Set up the report html
        result_directory = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(result_directory)

        #call dot
        print("Calling dot")
        graph_ofilename = result_directory + "/Graph.png"
        print(graph_ofilename)
        call_dot = "dot " + dotfilename + " -Tpng -o" + graph_ofilename
        os.system(call_dot)
        print("dot called")

        ### STEP 5 - Save and HTML report
        html_stats = []
        with open(outfilename) as f:
                html_stats += f.readlines()
        #Test the new HTML report
        report_file = self.scratch + "/report.html"
        report_html = open(report_file, "w+")
        report_html.write("\n".join(html_stats))
        report_html.close()

        dummy_html_report_runner = ReportUtil(self.config)
        output = dummy_html_report_runner._generate_report(params, result_directory, html_stats)
        #END DecisionTree

        # At some point might do deeper type checking...
        if not isinstance(output, dict):
            raise ValueError('Method DecisionTree return value ' +
                             'output is not type dict as required.')
        # return the results
        return [output]

    def status(self, ctx):
        #BEGIN_STATUS
        returnVal = {'state': "OK",
                     'message': "",
                     'version': self.VERSION,
                     'git_url': self.GIT_URL,
                     'git_commit_hash': self.GIT_COMMIT_HASH}
        #END_STATUS
        return [returnVal]
